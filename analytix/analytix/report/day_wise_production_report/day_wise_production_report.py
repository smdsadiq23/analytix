# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

# import frappe

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": "Process Date",
            "fieldname": "process_date",
            "fieldtype": "Date",
            "width": 110
        },
        {
            "label": "Department",
            "fieldname": "department",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Buyer",
            "fieldname": "buyer",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Season",
            "fieldname": "season",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Style",
            "fieldname": "style",
            "fieldtype": "Data",
            "width": 130
        },
        {
            "label": "Colour",
            "fieldname": "colour",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Size",
            "fieldname": "size",
            "fieldtype": "Data",
            "width": 80
        },
        {
            "label": "Order Qty",
            "fieldname": "order_qty",
            "fieldtype": "Int",
            "width": 110
        },
        {
            "label": "Completed Qty",
            "fieldname": "completed_qty",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": "Balance Qty",
            "fieldname": "balance_qty",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": "Completed %",
            "fieldname": "completed_percent",
            "fieldtype": "Percent",
            "width": 120
        }
    ]


def get_data(filters):

    conditions = []

    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) = %(date)s")

    if filters.get("department"):
        conditions.append("pc.name = %(department)s")

    if filters.get("buyer"):
        conditions.append("so.customer_name = %(buyer)s")

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")

    condition_sql = ""
    if conditions:
        condition_sql = " AND " + " AND ".join(conditions)

    query = f"""
        SELECT
            DATE(isl.logged_time) AS process_date,
            pc.cell_name AS department,
            so.customer_name AS buyer,
            stm.custom_season AS season,
            itm.custom_style_master AS style,
            itm.custom_colour_name AS colour,
            tbc.size AS size,
            COALESCE(SUM(soi.custom_order_qty), 0) AS order_qty,
            COALESCE(SUM(pi.quantity), 0) AS completed_qty,
            (COALESCE(SUM(pi.quantity), 0) -
             COALESCE(SUM(soi.custom_order_qty), 0)) AS balance_qty,
            CASE 
                WHEN COALESCE(SUM(soi.custom_order_qty), 0) = 0 THEN 0
                ELSE ROUND(
                    (COALESCE(SUM(pi.quantity), 0) /
                     COALESCE(SUM(soi.custom_order_qty), 0)) * 100, 2
                )
            END AS completed_percent
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor
            ON tor.name = tbc.parent
        INNER JOIN `tabItem` itm
            ON itm.name = tor.item
        INNER JOIN `tabProduction Item` pi
            ON pi.tracking_order = tor.name
            AND pi.bundle_configuration = tbc.name
        INNER JOIN `tabStyle Master` stm
            ON stm.name = itm.custom_style_master
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabItem Scan Log` isl
            ON isl.production_item = pi.name
            AND isl.operation = tor.last_operation
            AND isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
        INNER JOIN `tabPhysical Cell` pc 
            ON pc.name = isl.physical_cell
        INNER JOIN `tabSales Order` so
            ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi
            ON soi.parent = so.name
            AND soi.custom_style = itm.custom_style_master
            AND soi.custom_color = itm.custom_colour_name
            AND soi.custom_size = tbc.size
        WHERE 1=1 {condition_sql}
        GROUP BY 
            DATE(isl.logged_time),
            pc.cell_name,
            so.customer_name,
            stm.custom_season,
            itm.custom_style_master,
            itm.custom_colour_name,
            tbc.size
        ORDER BY process_date DESC
    """

    return frappe.db.sql(query, filters, as_dict=True)