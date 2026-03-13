# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Buyer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 200,
        },
        {
            "label": "Style",
            "fieldname": "custom_style_master",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": "OCN",
            "fieldname": "ocn",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 180,
        },
        {
            "label": "Colour",
            "fieldname": "fg_item_colour",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Order Qty (Kgs)",
            "fieldname": "order_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Received Qty (Kgs)",
            "fieldname": "total_received_quantity",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": "Bal Qty (Kgs)",
            "fieldname": "bal_qty",
            "fieldtype": "Float",
            "width": 120,
        },
    ]


def get_data(filters=None):
    filters = filters or {}

    # ----------------------------------------------------------------
    # Step 1: One GRN OCN FG Mapping row per GRN (first row by name)
    # ----------------------------------------------------------------
    grn_conditions = ""
    grn_values = {}

    if filters.get("from_date"):
        grn_conditions += " AND grn.posting_date >= %(from_date)s"
        grn_values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        grn_conditions += " AND grn.posting_date <= %(to_date)s"
        grn_values["to_date"] = filters["to_date"]

    grn_rows = frappe.db.sql(
        """
        SELECT
            grnofm.parent   AS grn,
            grnofm.ocn,
            grnofm.fg_item,
            grnofm.fg_item_colour,
            grn.posting_date,
            grn.total_received_quantity
        FROM `tabGRN OCN FG Mapping` grnofm
        INNER JOIN `tabGoods Receipt Note` grn
            ON grn.name = grnofm.parent
        WHERE grnofm.name = (
            SELECT name
            FROM `tabGRN OCN FG Mapping` sub
            WHERE sub.parent = grnofm.parent
            ORDER BY sub.name ASC
            LIMIT 1
        )
        {conditions}
        ORDER BY grnofm.parent
        """.format(conditions=grn_conditions),
        grn_values,
        as_dict=True,
    )

    if not grn_rows:
        return []

    # ----------------------------------------------------------------
    # Step 2: Collect unique keys for targeted lookups
    # ----------------------------------------------------------------
    ocn_list  = list({r.ocn for r in grn_rows})
    item_list = list({r.fg_item for r in grn_rows})

    # ----------------------------------------------------------------
    # Step 3: Fetch customer per Sales Order
    # ----------------------------------------------------------------
    so_rows = frappe.db.sql(
        "SELECT name, customer FROM `tabSales Order` WHERE name IN %(ocn_list)s",
        {"ocn_list": ocn_list},
        as_dict=True,
    )
    # { ocn -> customer }
    so_customer_map = {r.name: r.customer for r in so_rows}

    # ----------------------------------------------------------------
    # Step 4: Fetch style master + default_bom from Item
    # ----------------------------------------------------------------
    item_rows = frappe.db.sql(
        """
        SELECT name, custom_style_master, default_bom
        FROM `tabItem`
        WHERE name IN %(item_list)s
        """,
        {"item_list": item_list},
        as_dict=True,
    )
    # { item_code -> custom_style_master }
    item_style_map = {r.name: r.custom_style_master for r in item_rows}
    # { item_code -> default_bom }
    item_bom_map   = {r.name: r.default_bom for r in item_rows}

    # ----------------------------------------------------------------
    # Step 5: Fetch qty_consumed_per_unit from BOM Item
    #         parentfield = custom_fabrics_items
    # ----------------------------------------------------------------
    bom_list = list({bom for bom in item_bom_map.values() if bom})

    bom_fabric_map = {}  # { bom -> qty_consumed_per_unit }

    if bom_list:
        bom_rows = frappe.db.sql(
            """
            SELECT parent, qty_consumed_per_unit
            FROM `tabBOM Item`
            WHERE parent IN %(bom_list)s
              AND parentfield = 'custom_fabrics_items'
            """,
            {"bom_list": bom_list},
            as_dict=True,
        )
        # If multiple fabric rows exist per BOM, sum them up
        for r in bom_rows:
            bom_fabric_map[r.parent] = (
                bom_fabric_map.get(r.parent, 0) + (r.qty_consumed_per_unit or 0)
            )

    # ----------------------------------------------------------------
    # Step 6: Fetch SO Item qty — grouped by (parent, item_code, colour)
    # ----------------------------------------------------------------
    soi_rows = frappe.db.sql(
        """
        SELECT
            parent,
            item_code,
            custom_color,
            SUM(qty) AS so_item_qty
        FROM `tabSales Order Item`
        WHERE parent IN %(ocn_list)s
        GROUP BY parent, item_code, custom_color
        """,
        {"ocn_list": ocn_list},
        as_dict=True,
    )
    # { (ocn, item_code, colour) -> so_item_qty }
    soi_qty_map = {
        (r.parent, r.item_code, r.custom_color): r.so_item_qty
        for r in soi_rows
    }

    # ----------------------------------------------------------------
    # Step 7: Assemble final result in Python
    # ----------------------------------------------------------------
    data = []
    for row in grn_rows:
        customer = so_customer_map.get(row.ocn)

        so_item_qty  = soi_qty_map.get((row.ocn, row.fg_item, row.fg_item_colour), 0) or 0
        default_bom  = item_bom_map.get(row.fg_item)
        qty_per_unit = bom_fabric_map.get(default_bom, 0) if default_bom else 0

        order_qty    = so_item_qty * qty_per_unit
        received_qty = row.total_received_quantity or 0
        bal_qty      = received_qty - order_qty

        data.append({
            "posting_date":            row.posting_date,
            "customer":                customer,
            "custom_style_master":     item_style_map.get(row.fg_item),
            "ocn":                     row.ocn,
            "fg_item_colour":          row.fg_item_colour,
            "order_qty":               order_qty,
            "total_received_quantity": received_qty,
            "bal_qty":                 bal_qty,
        })

    return data