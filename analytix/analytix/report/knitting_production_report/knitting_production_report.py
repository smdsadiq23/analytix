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
        {"label": "Date",               "fieldname": "process_date",        "fieldtype": "Date",    "width": 110},
        {"label": "Buyer",              "fieldname": "buyer",               "fieldtype": "Data",    "width": 150},
        {"label": "Season",             "fieldname": "season",              "fieldtype": "Data",    "width": 100},
        {"label": "Delivery Date",      "fieldname": "delivery_date",       "fieldtype": "Data",    "width": 120},
        {"label": "Style",              "fieldname": "style",               "fieldtype": "Data",    "width": 140},
        {"label": "Colour",             "fieldname": "colour",              "fieldtype": "Data",    "width": 120},
        {"label": "Size",               "fieldname": "size",                "fieldtype": "Data",    "width": 60},
        {"label": "Order Qty",          "fieldname": "order_qty",           "fieldtype": "Int",     "width": 100},
        {"label": "Planned Qty",        "fieldname": "planned_qty",         "fieldtype": "Int",     "width": 100},
        {"label": "Today Output",       "fieldname": "today_output",        "fieldtype": "Int",     "width": 110},
        {"label": "Cumulative Output",  "fieldname": "cumulative_output",   "fieldtype": "Int",     "width": 140},
        {"label": "Balance Qty",        "fieldname": "balance_qty",         "fieldtype": "Int",     "width": 110},
        {"label": "Completed %",        "fieldname": "completed_pct",       "fieldtype": "Data",    "width": 110},
        {"label": "Planned Wt",         "fieldname": "planned_weight",      "fieldtype": "Float",   "width": 130},
        {"label": "Actual Wt",          "fieldname": "actual_weight",       "fieldtype": "Float",   "width": 130},
        {"label": "Yield %",            "fieldname": "yield_pct",           "fieldtype": "Data",    "width": 100},
        {"label": "Wastage/Excess",     "fieldname": "wastage_excess",      "fieldtype": "Data",    "width": 120},
    ]


def get_order_map(filters):
    """Order qty, planned qty, delivery date, season — keyed by (style, colour, size)."""
    conditions = []
    params     = {}

    if filters.get("buyer"):
        conditions.append("so.customer = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    where = " AND ".join(conditions) if conditions else "1=1"

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            so.customer_name                            AS buyer,
            so.delivery_date                            AS delivery_date,
            stm.custom_season                           AS season,
            COALESCE(SUM(soi.custom_order_qty), 0)      AS order_qty,
            COALESCE(SUM(soi.qty), 0)                   AS planned_qty
        FROM (
            SELECT DISTINCT parent, sales_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
        INNER JOIN `tabSales Order` so          ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi    ON soi.parent = so.name AND soi.custom_size = tbc.size
        INNER JOIN `tabTracking Order` tor      ON tor.name = tbc.parent
        INNER JOIN `tabItem` itm                ON itm.name = tor.item
        INNER JOIN `tabStyle Master` stm        ON stm.name = itm.custom_style_master
        WHERE {where}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size,
                 so.customer_name, so.delivery_date, stm.custom_season
    """, params, as_dict=True)

    return {(r.style, r.colour, r.size): r for r in rows}


def get_daily_production(filters):
    """
    KNITTING OUT completed on exactly the selected date.
    Grouped by date / style / colour / size.
    Also fetches unit_planned_weight from Work Order Line Item
    so planned weight can be calculated per row in Python.
    """
    conditions = [
        "pc.cell_name = 'KNITTING'",
        "isl.operation = 'KNITTING OUT'",
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Pass')",
    ]
    params = {}

    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) = %(date)s")
        params["date"] = filters["date"]

    if filters.get("buyer"):
        conditions.append("so.customer = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    where = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
            DATE(isl.logged_time)                       AS process_date,
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            SUM(pi.quantity)                            AS today_output,
            SUM(isl.custom_actual_weight)               AS actual_weight,
            MAX(wol.custom_planned_weight)              AS unit_planned_weight
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
            ON tbc.parent = tor.name AND tbc.name = pi.bundle_configuration
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        INNER JOIN `tabWork Order Line Item` wol
            ON wol.parent = tbc.work_order AND wol.size = tbc.size
        WHERE {where}
        GROUP BY DATE(isl.logged_time), itm.custom_style_master,
                 itm.custom_colour_name, tbc.size
        ORDER BY process_date DESC, itm.custom_style_master, tbc.size
    """, params, as_dict=True)


def get_cumulative_map(filters):
    """
    Total KNITTING output from beginning up to and including selected date.
    Grouped only by style / colour / size (cross-operator, cross-date total).
    """
    conditions = [
        "pc.cell_name = 'KNITTING'",
        "isl.operation = 'KNITTING OUT'",
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Pass')",
    ]
    params = {}

    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) <= %(date)s")
        params["date"] = filters["date"]

    if filters.get("buyer"):
        conditions.append("so.customer = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    where = " AND ".join(conditions)

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            COALESCE(SUM(pi.quantity), 0)               AS cumulative_output
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
            ON tbc.parent = tor.name AND tbc.name = pi.bundle_configuration
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE {where}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """, params, as_dict=True)

    return {(r.style, r.colour, r.size): int(r.cumulative_output) for r in rows}


def get_data(filters):
    order_map      = get_order_map(filters)
    daily_logs     = get_daily_production(filters)
    cumulative_map = get_cumulative_map(filters)

    result = []

    for log in daily_logs:
        key = (log.style, log.colour, log.size)

        order_info        = order_map.get(key)
        order_qty         = int(order_info.order_qty)  if order_info else 0
        planned_qty       = int(order_info.planned_qty) if order_info else 0

        today_output      = int(log.today_output or 0)
        cumulative_output = cumulative_map.get(key, today_output)
        actual_weight     = round(float(log.actual_weight or 0), 3)

        # Planned weight = today's output qty × per-unit planned weight
        unit_plnd      = float(log.unit_planned_weight or 0)
        planned_weight = round(today_output * unit_plnd, 3)

        # Balance Qty = Planned Qty − Cumulative Output
        balance_qty = planned_qty - cumulative_output

        # Completed % = (Cumulative Output / Order Qty) × 100
        completed_pct     = round((cumulative_output / order_qty) * 100, 1) if order_qty else 0.0
        completed_pct_str = f"{completed_pct:.1f}%"

        # Yield % = (Actual Wt / Planned Wt) × 100  — > 100% means over-consumed
        yield_pct     = round((actual_weight / planned_weight) * 100, 2) if planned_weight else 0.0
        yield_pct_str = f"{yield_pct:.1f}%"

        # Wastage/Excess: positive = saved (good), negative = over-used (bad)
        wastage_excess     = round(((actual_weight - planned_weight) / planned_weight) * 100, 2) if planned_weight else 0.0
        wastage_excess_str = f"{wastage_excess:+.1f}%"

        # Format delivery date
        delivery_date = ""
        if order_info and order_info.delivery_date:
            delivery_date = formatdate(order_info.delivery_date, "dd-mm-yyyy")

        result.append({
            "process_date":      log.process_date,
            "buyer":             order_info.buyer  if order_info else "",
            "season":            order_info.season if order_info else "",
            "delivery_date":     delivery_date,
            "_delivery_date_raw": order_info.delivery_date if order_info else None,
            "style":             log.style,
            "colour":            log.colour,
            "size":              log.size,
            "order_qty":         order_qty,
            "planned_qty":       planned_qty,
            "today_output":      today_output,
            "cumulative_output": cumulative_output,
            "balance_qty":       balance_qty,
            "completed_pct":     completed_pct_str,
            "planned_weight":    planned_weight,
            "actual_weight":     actual_weight,
            "yield_pct":         yield_pct_str,
            "wastage_excess":    wastage_excess_str,
        })

    # ── Sort by delivery date descending, None last ───────────────────────
    result.sort(key=lambda r: (r["_delivery_date_raw"] or "0000-00-00"), reverse=True)
    for r in result:
        r.pop("_delivery_date_raw", None)

    # # ── TOTAL / AVERAGE row ────────────────────────────────────────────────
    # if result:
    #     total_order      = sum(r["order_qty"]         for r in result)
    #     total_planned    = sum(r["planned_qty"]        for r in result)
    #     total_today      = sum(r["today_output"]       for r in result)
    #     total_cumulative = sum(r["cumulative_output"]  for r in result)
    #     total_balance    = sum(r["balance_qty"]        for r in result)
    #     total_plnd_wt    = round(sum(r["planned_weight"] for r in result), 3)
    #     total_actual_wt  = round(sum(r["actual_weight"]  for r in result), 3)

    #     avg_yield      = round((total_actual_wt / total_plnd_wt) * 100, 1) if total_plnd_wt else 0.0
    #     total_wastage  = round(((total_actual_wt - total_plnd_wt) / total_plnd_wt) * 100, 1) if total_plnd_wt else 0.0
    #     total_completed = round((total_cumulative / total_order) * 100, 1) if total_order else 0.0

    #     result.append({
    #         "row_num":           None,
    #         "process_date":      None,
    #         "buyer":             "TOTAL / AVERAGE",
    #         "season":            "",
    #         "delivery_date":     "",
    #         "style":             "",
    #         "colour":            "",
    #         "size":              "",
    #         "order_qty":         total_order,
    #         "planned_qty":       total_planned,
    #         "today_output":      total_today,
    #         "cumulative_output": total_cumulative,
    #         "balance_qty":       total_balance,
    #         "completed_pct":     f"{total_completed:.1f}%",
    #         "planned_weight":    total_plnd_wt,
    #         "actual_weight":     total_actual_wt,
    #         "yield_pct":         f"{avg_yield:.1f}%",
    #         "wastage_excess":    f"{total_wastage:+.1f}%",
    #     })

    return result