# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import formatdate


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data    = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": "Date",                   "fieldname": "process_date",           "fieldtype": "Date",    "width": 120},        
        {"label": "Department",             "fieldname": "department",             "fieldtype": "Data",    "width": 130},
        {"label": "Buyer",                  "fieldname": "buyer",                  "fieldtype": "Data",    "width": 150},
        {"label": "Season",                 "fieldname": "season",                 "fieldtype": "Data",    "width": 100},
        {"label": "Delivery Date",          "fieldname": "delivery_date",          "fieldtype": "Data",    "width": 130},
        {"label": "Style",                  "fieldname": "style",                  "fieldtype": "Data",    "width": 140},
        {"label": "Colour",                 "fieldname": "colour",                 "fieldtype": "Data",    "width": 120},
        {"label": "Size",                   "fieldname": "size",                   "fieldtype": "Data",    "width": 80},
        {"label": "Order Qty",              "fieldname": "order_qty",              "fieldtype": "Int",     "width": 100},
        {"label": "Day Completed Qty",      "fieldname": "completed_qty",          "fieldtype": "Int",     "width": 140},
        {"label": "Cumulative Completed",   "fieldname": "cumulative_completed_qty","fieldtype": "Int",    "width": 160},
        {"label": "Balance Qty",            "fieldname": "balance_qty",            "fieldtype": "Int",     "width": 110},
        {"label": "Completed %",            "fieldname": "completed_percent",      "fieldtype": "Percent", "width": 120},
    ]


def get_order_map(filters):
    """Fetches static order details mapped by (style, colour, size)."""
    conditions = []
    params     = {}

    if filters.get("buyer"):
        conditions.append("so.customer_name = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            itm.custom_style_master     AS style,
            itm.custom_colour_name      AS colour,
            tbc.size                    AS size,
            so.customer_name            AS buyer,
            so.delivery_date            AS delivery_date,
            stm.custom_season           AS season,
            COALESCE(SUM(soi.custom_order_qty), 0) AS order_qty
        FROM (
            SELECT DISTINCT parent, sales_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
        INNER JOIN `tabSales Order` so          ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi    ON soi.parent = so.name
        INNER JOIN `tabTracking Order` tor      ON tor.name = tbc.parent
        INNER JOIN `tabItem` itm                ON itm.name = tor.item
        INNER JOIN `tabStyle Master` stm        ON stm.name = itm.custom_style_master
        WHERE tbc.parentfield = 'bundle_configurations'
            AND {where_clause}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size,
                 so.customer_name, stm.custom_season
    """

    rows = frappe.db.sql(query, params, as_dict=True)
    return {(r.style, r.colour, r.size): r for r in rows}


def get_production_data(filters):
    """Daily completed qty — filtered to exactly the selected date."""
    conditions = []
    params     = {}

    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) = %(date)s")
        params["date"] = filters["date"]

    if filters.get("department"):
        conditions.append("pc.name = %(department)s")
        params["department"] = filters["department"]

    if filters.get("buyer"):
        conditions.append("so.customer_name = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            DATE(isl.logged_time)       AS process_date,
            pc.cell_name                AS department,
            itm.custom_style_master     AS style,
            itm.custom_colour_name      AS colour,
            tbc.size                    AS size,
            COALESCE(SUM(pi.quantity), 0) AS completed_qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
            ON tbc.parent = tor.name AND tbc.parentfield = 'bundle_configurations'
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
            ON pcflo.parent = tbc.work_order
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE isl.operation = pcflo.last_operation
            AND isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
            AND {where_clause}
        GROUP BY DATE(isl.logged_time), pc.cell_name,
                 itm.custom_style_master, itm.custom_colour_name, tbc.size
        ORDER BY process_date DESC, pc.cell_name, itm.custom_style_master, tbc.size
    """

    return frappe.db.sql(query, params, as_dict=True)


def get_cumulative_data(filters):
    """
    Cumulative completed qty from the beginning up to and including
    the selected date, grouped only by style/colour/size.
    Department filter is intentionally excluded — cumulative is cross-department.
    """
    conditions = []
    params     = {}

    # Use <= date so we capture everything up to the selected date
    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) <= %(date)s")
        params["date"] = filters["date"]

    if filters.get("buyer"):
        conditions.append("so.customer_name = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            itm.custom_style_master     AS style,
            itm.custom_colour_name      AS colour,
            tbc.size                    AS size,
            COALESCE(SUM(pi.quantity), 0) AS cumulative_completed_qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
            ON tbc.parent = tor.name AND tbc.parentfield = 'bundle_configurations'
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
            ON pcflo.parent = tbc.work_order
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE isl.operation = pcflo.last_operation
            AND isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
            AND {where_clause}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """

    rows = frappe.db.sql(query, params, as_dict=True)
    # Key by (style, colour, size) for O(1) lookup in get_data
    return {(r.style, r.colour, r.size): int(r.cumulative_completed_qty) for r in rows}


def get_data(filters):
    order_map       = get_order_map(filters)
    if not order_map:
        return []

    production_logs = get_production_data(filters)
    cumulative_map  = get_cumulative_data(filters)   # ← new

    result = []

    for log in production_logs:
        key = (log.style, log.colour, log.size)

        if key not in order_map:
            continue

        order_info    = order_map[key]
        order_qty     = int(order_info.order_qty)
        completed_qty = int(log.completed_qty)

        # Cumulative — fall back to daily qty if somehow missing
        cumulative_completed_qty = cumulative_map.get(key, completed_qty)

        # Balance and % now based on cumulative, not daily
        balance_qty       = cumulative_completed_qty - order_qty
        completed_percent = round((cumulative_completed_qty / order_qty) * 100, 2) if order_qty > 0 else 0.0
        completed_percent_str = f"{completed_percent:.1f}%"

        delivery_date = ""
        if order_info.delivery_date:
            delivery_date = formatdate(order_info.delivery_date, "dd-mm-yyyy")

        result.append({
            "process_date":            log.process_date,
            "delivery_date":           delivery_date,
            "department":              log.department,
            "buyer":                   order_info.buyer,
            "season":                  order_info.season,
            "style":                   log.style,
            "colour":                  log.colour,
            "size":                    log.size,
            "order_qty":               order_qty,
            "completed_qty":           completed_qty,           # daily — for reference
            "cumulative_completed_qty": cumulative_completed_qty, # up to selected date
            "balance_qty":             balance_qty,             # based on cumulative
            "completed_percent":       completed_percent_str,   # based on cumulative
        })

    return result