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
            "label": "Unit",
            "fieldname": "unit",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": "Merchant",
            "fieldname": "merchant",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "OCN",
            "fieldname": "ocn",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 180,
        },
        {
            "label": "Style",
            "fieldname": "style",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": "Colour",
            "fieldname": "colour",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": "Fabric Ordered",
            "fieldname": "fabric_ordered",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": "Fabric Received",
            "fieldname": "fabric_received",
            "fieldtype": "Float",
            "width": 130,
        },
        {
            "label": "Balance to Receive",
            "fieldname": "balance_to_receive",
            "fieldtype": "Float",
            "width": 150,
        },
        {
            "label": "Can Cut %",
            "fieldname": "can_cut_percent",
            "fieldtype": "Percent",
            "width": 110,
        },
        {
            "label": "Responsible",
            "fieldname": "responsible",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Last Inhouse Date",
            "fieldname": "last_inhouse_date",
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "label": "Merchant Remarks",
            "fieldname": "remarks",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": "Fabric Remarks",
            "fieldname": "fabric_remarks",
            "fieldtype": "Date",
            "width": 140,
        },
        {
            "label": "Manager Remarks",
            "fieldname": "manager_remarks",
            "fieldtype": "Data",
            "width": 160,
        },
    ]


def get_data(filters=None):
    filters = filters or {}

    # ----------------------------------------------------------------
    # Step 1: Latest Can Cut per (ocn, colour) where can_cut_percent <= 98
    #
    #   When multiple Can Cuts exist for the same OCN+colour, only the
    #   most recently created one is used to determine eligibility and
    #   the Responsible field.  If the latest doc is > 98% the pair is
    #   excluded even if an earlier one was <= 98%.
    # ----------------------------------------------------------------
    cc_conditions = ""
    cc_values = {}

    if filters.get("customer"):
        cc_conditions += " AND so.customer = %(customer)s"
        cc_values["customer"] = filters["customer"]

    if filters.get("responsible"):
        cc_conditions += " AND cc.deviation_under = %(responsible)s"
        cc_values["responsible"] = filters["responsible"]

    can_cut_rows = frappe.db.sql(
        """
        SELECT
            usr.full_name       AS merchant,
            fbu.factory_name    AS unit,
            cc.sales_order      AS ocn,
            cc.style,
            cc.colour,
            cc.deviation_under  AS responsible,
            cc.can_cut_percent
        FROM `tabCan Cut` cc
        INNER JOIN `tabSales Order` so
            ON so.name = cc.sales_order
        -- Restrict to the latest Can Cut per (ocn, colour)
        INNER JOIN (
            SELECT sales_order, colour, MAX(creation) AS max_creation
            FROM `tabCan Cut`
            WHERE docstatus = 1
            GROUP BY sales_order, colour
        ) latest
            ON  latest.sales_order  = cc.sales_order
            AND latest.colour       = cc.colour
            AND latest.max_creation = cc.creation
        LEFT JOIN `tabUser` usr ON cc.merchant = usr.name
        LEFT JOIN `tabFactory Business Unit` fbu ON cc.factory_business_unit = fbu.name        
        WHERE cc.docstatus = 1
          AND cc.can_cut_percent <= 98
          {conditions}
        ORDER BY cc.sales_order, cc.colour
        """.format(conditions=cc_conditions),
        cc_values,
        as_dict=True,
    )

    if not can_cut_rows:
        return []

    ocn_list = list({r.ocn for r in can_cut_rows})

    # Normalise colour to uppercase on Can Cut rows so keys match GRN map
    for r in can_cut_rows:
        r.colour = (r.colour or "").upper()

    # ----------------------------------------------------------------
    # Step 2: GRN receipts per (ocn, fg_item, fg_item_colour)
    #         Carries fg_item forward for the BOM lookup.
    #         Date filters scope which GRNs count as "received".
    # ----------------------------------------------------------------
    # Build GRN map using the same 3-strategy fallback used elsewhere
    grn_map = _get_grn_data(ocn_list)
    # Flatten to a list so item_set collection below still works
    grn_rows = list(grn_map.values())

    # ----------------------------------------------------------------
    # Step 3: SO Item qty per (ocn, item_code, colour)
    #         Used for the BOM-calculated fabric_ordered.
    # ----------------------------------------------------------------
    soi_rows = frappe.db.sql(
        """
        SELECT
            parent       AS ocn,
            item_code,
            custom_color AS colour,
            SUM(qty)     AS so_qty
        FROM `tabSales Order Item`
        WHERE parent IN %(ocn_list)s
        GROUP BY parent, item_code, custom_color
        """,
        {"ocn_list": ocn_list},
        as_dict=True,
    )

    # { (ocn, colour) -> { item_code, so_qty } }  — colour uppercased for consistent keying
    soi_map = {(r.ocn, (r.colour or "").upper()): r for r in soi_rows}

    # ----------------------------------------------------------------
    # Step 3: Collect all item codes (from GRN + SO Items) for lookup
    # ----------------------------------------------------------------
    item_set = {r.fg_item for r in grn_rows if r.get("fg_item")}
    item_set.update(r.item_code for r in soi_rows)
    item_list = list(item_set)

    # ----------------------------------------------------------------
    # Step 5: Item master — default_bom + custom_style_master
    # ----------------------------------------------------------------
    item_bom_map   = {}
    item_style_map = {}

    if item_list:
        item_rows = frappe.db.sql(
            """
            SELECT name, default_bom, custom_style_master
            FROM `tabItem`
            WHERE name IN %(item_list)s
            """,
            {"item_list": item_list},
            as_dict=True,
        )
        item_bom_map   = {r.name: r.default_bom        for r in item_rows}
        item_style_map = {r.name: r.custom_style_master for r in item_rows}

    # ----------------------------------------------------------------
    # Step 6: BOM fabric consumption per unit
    #         parentfield = 'custom_fabrics_items'; sum across multiple
    #         fabric rows that may exist in a single BOM.
    # ----------------------------------------------------------------
    bom_list = list({bom for bom in item_bom_map.values() if bom})
    bom_fabric_map = {}   # { bom -> { qty, uom } }

    if bom_list:
        bom_rows = frappe.db.sql(
            """
            SELECT
                parent,
                SUM(qty_consumed_per_unit) AS total_qty,
                stock_uom
            FROM `tabBOM Item`
            WHERE parent     IN %(bom_list)s
              AND parentfield = 'custom_fabrics_items'
            GROUP BY parent, stock_uom
            """,
            {"bom_list": bom_list},
            as_dict=True,
        )
        for r in bom_rows:
            bom_fabric_map[r.parent] = {
                "qty": r.total_qty or 0,
                "uom": r.stock_uom or "",
            }

    # ----------------------------------------------------------------
    # Step 7: Saved Remarks
    # ----------------------------------------------------------------
    try:
        remark_rows = frappe.db.sql(
            """
            SELECT ocn, colour, remarks, manager_remarks, fabric_remarks
            FROM `tabFabric Inhouse Remark`
            WHERE ocn IN %(ocn_list)s
            """,
            {"ocn_list": ocn_list},
            as_dict=True,
        )
        remark_map = {(r.ocn, (r.colour or "").upper()): r for r in remark_rows}
    except Exception:
        remark_map = {}

    # ----------------------------------------------------------------
    # Step 8: Assemble final rows
    # ----------------------------------------------------------------
    normal_rows   = []
    remarked_rows = []

    for row in can_cut_rows:
        key = (row.ocn, row.colour)

        # Resolve item_code — GRN mapping is authoritative; fall back to SO Item
        grn_data  = grn_map.get(key, {})
        item_code = grn_data.get("fg_item") or (soi_map.get(key) or {}).get("item_code")

        # GRN receipt totals
        fabric_received = grn_data.get("fabric_received") or 0
        last_inhouse    = grn_data.get("last_inhouse_date")

        # BOM-calculated Fabric Ordered
        #   = SO qty for (ocn, colour)  ×  BOM fabric qty per finished unit
        soi_data     = soi_map.get(key, {})
        so_qty       = soi_data.get("so_qty") or 0
        default_bom  = item_bom_map.get(item_code) if item_code else None
        bom_data     = bom_fabric_map.get(default_bom, {}) if default_bom else {}
        qty_per_unit = bom_data.get("qty", 0)
        uom          = bom_data.get("uom", "")
        fabric_ordered = so_qty * qty_per_unit

        balance = fabric_received - fabric_ordered

        # Rule 3: drop rows where balance >= 0 (fully or over received)
        if balance >= 0:
            continue

        saved           = remark_map.get(key, {})
        remarks         = saved.get("remarks") or ""
        manager_remarks = saved.get("manager_remarks") or ""
        fabric_remarks      = saved.get("fabric_remarks")

        # Style: Can Cut field is preferred; fall back to Item master
        style = row.style or (item_style_map.get(item_code) if item_code else "")

        entry = {
            "unit":               row.unit,
            "merchant":           row.merchant,
            "ocn":                row.ocn,
            "style":              style,
            "colour":             row.colour,
            "fabric_ordered":     fabric_ordered,
            "fabric_received":    fabric_received,
            "balance_to_receive": balance,
            "can_cut_percent":    row.can_cut_percent,
            "responsible":        row.responsible,
            "last_inhouse_date":  last_inhouse,
            "remarks":            remarks,
            "manager_remarks":    manager_remarks,
            "fabric_remarks":     fabric_remarks,
            # Hidden — used by JS for uom tooltip / display
            "_uom":               uom,
        }

        # Rule 4: both remarks set → push to bottom
        if remarks and manager_remarks:
            remarked_rows.append(entry)
        else:
            normal_rows.append(entry)

    return normal_rows + remarked_rows


def _get_grn_data(ocn_list):
    """
    Return a dict  { (ocn, colour) -> row }  with fabric_received and
    last_inhouse_date for every OCN in ocn_list.

    All three strategies run for ALL OCNs.  Coverage is tracked at the
    (ocn, colour) pair level — not OCN level — so a mixed OCN that has
    some colours in the new mapping system and other colours only in old
    GRNs is handled correctly.  Strategy 1 takes precedence; Strategy 2
    fills gaps; Strategy 3 fills remaining gaps.
    """
    grn_map = {}   # { (ocn, colour) -> frappe._dict }

    # ------------------------------------------------------------------
    # Strategy 1: tabGRN OCN FG Mapping  (current system)
    # ------------------------------------------------------------------
    s1_rows = frappe.db.sql(
        """
        SELECT
            grnofm.ocn,
            grnofm.fg_item,
            grnofm.fg_item_colour            AS colour,
            MAX(grn.posting_date)            AS last_inhouse_date,
            SUM(grn.total_received_quantity) AS fabric_received
        FROM `tabGRN OCN FG Mapping` grnofm
        INNER JOIN `tabGoods Receipt Note` grn
            ON grn.name = grnofm.parent
        WHERE grnofm.ocn IN %(ocn_list)s
          AND grn.docstatus = 1
        GROUP BY grnofm.ocn, grnofm.fg_item, grnofm.fg_item_colour
        """,
        {"ocn_list": ocn_list},
        as_dict=True,
    )

    for r in s1_rows:
        r.colour = (r.colour or "").upper().strip()
        grn_map[(r.ocn, r.colour)] = r

    # ------------------------------------------------------------------
    # Strategy 2: fg_item on GRN header  (legacy)
    #             Only fills (ocn, colour) pairs not already in grn_map.
    # ------------------------------------------------------------------
    s2_rows = frappe.db.sql(
        """
        SELECT
            grn.ocn,
            grn.fg_item,
            gri.color                        AS colour,
            MAX(grn.posting_date)            AS last_inhouse_date,
            SUM(gri.received_quantity)       AS fabric_received
        FROM `tabGoods Receipt Note` grn
        INNER JOIN `tabGoods Receipt Item` gri
            ON gri.parent = grn.name
        WHERE grn.ocn IN %(ocn_list)s
          AND grn.docstatus = 1
          AND grn.fg_item IS NOT NULL
          AND grn.fg_item != ''
        GROUP BY grn.ocn, grn.fg_item, gri.color
        """,
        {"ocn_list": ocn_list},
        as_dict=True,
    )

    for r in s2_rows:
        r.colour = (r.colour or "").upper().strip()
        key = (r.ocn, r.colour)
        if key not in grn_map:
            grn_map[key] = r

    # ------------------------------------------------------------------
    # Strategy 3: Old GRNs — no fg_item, no mapping entries.
    #             Colour resolved from tabGoods Receipt Item.color.
    #             Only fills (ocn, colour) pairs not already found.
    # ------------------------------------------------------------------
    s3_rows = frappe.db.sql(
        """
        SELECT
            grn.ocn,
            NULL                             AS fg_item,
            gri.color                        AS colour,
            MAX(grn.posting_date)            AS last_inhouse_date,
            SUM(gri.received_quantity)       AS fabric_received
        FROM `tabGoods Receipt Note` grn
        INNER JOIN `tabGoods Receipt Item` gri
            ON gri.parent = grn.name
        WHERE grn.ocn IN %(ocn_list)s
          AND grn.docstatus = 1
          AND (grn.fg_item IS NULL OR grn.fg_item = '')
          AND grn.name NOT IN (
              SELECT DISTINCT parent
              FROM `tabGRN OCN FG Mapping`
              WHERE parent IN (
                  SELECT name FROM `tabGoods Receipt Note`
                  WHERE ocn IN %(ocn_list)s
              )
          )
        GROUP BY grn.ocn, gri.color
        """,
        {"ocn_list": ocn_list},
        as_dict=True,
    )

    for r in s3_rows:
        r.colour = (r.colour or "").upper().strip()
        key = (r.ocn, r.colour)
        if key not in grn_map:
            grn_map[key] = r

    return grn_map


# ----------------------------------------------------------------
# Whitelisted API — called from JS on dropdown change
# ----------------------------------------------------------------
@frappe.whitelist()
def save_remark(ocn, colour, field, value):
    """Upsert a Remarks / Manager Remarks value for a report row."""
    if field not in ("remarks", "manager_remarks", "fabric_remarks"):
        frappe.throw("Invalid field: " + field)

    existing = frappe.db.get_value(
        "Fabric Inhouse Remark",
        {"ocn": ocn, "colour": colour},
        "name",
    )

    if existing:
        frappe.db.set_value("Fabric Inhouse Remark", existing, field, value)
    else:
        doc = frappe.get_doc({
            "doctype": "Fabric Inhouse Remark",
            "ocn":     ocn,
            "colour":  colour,
            field:     value,
        })
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return "ok"