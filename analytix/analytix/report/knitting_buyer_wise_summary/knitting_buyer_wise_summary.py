# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data    = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "#",                  "fieldname": "row_num",             "fieldtype": "Int",     "width": 50},
        {"label": "Buyer",              "fieldname": "buyer",               "fieldtype": "Data",    "width": 170},
        {"label": "Season",             "fieldname": "season",              "fieldtype": "Data",    "width": 100},
        {"label": "No. of Styles",      "fieldname": "style_count",         "fieldtype": "Int",     "width": 110},
        {"label": "Order Qty",          "fieldname": "order_qty",           "fieldtype": "Int",     "width": 100},
        {"label": "Planned Qty",        "fieldname": "planned_qty",         "fieldtype": "Int",     "width": 100},
        {"label": "Today Output",       "fieldname": "today_output",        "fieldtype": "Int",     "width": 110},
        {"label": "Cumulative Output",  "fieldname": "cumulative_output",   "fieldtype": "Int",     "width": 140},
        {"label": "Completed %",        "fieldname": "completed_pct",       "fieldtype": "Data",    "width": 110},
		{"label": "Balance Qty",        "fieldname": "balance_qty",         "fieldtype": "Int",     "width": 110},        
        {"label": "Planned Wt (kg)",    "fieldname": "planned_weight",      "fieldtype": "Float",   "width": 130},
        {"label": "Actual Wt (kg)",     "fieldname": "actual_weight",       "fieldtype": "Float",   "width": 130},
        {"label": "Variance (kg)",      "fieldname": "variance",            "fieldtype": "Float",   "width": 120},
        {"label": "Yield %",            "fieldname": "yield_pct",           "fieldtype": "Data",    "width": 100},
    ]


def get_order_map(filters):
    """
    Order qty per (style, colour, size) → also carries buyer / season.
    """
    conditions = []
    params     = {}

    if filters.get("buyer"):
        conditions.append("so.customer_name = %(buyer)s")
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
                 so.customer_name, stm.custom_season
    """, params, as_dict=True)

    return {(r.style, r.colour, r.size): r for r in rows}


def get_daily_production(filters):
    """KNITTING OUT completed on the selected date, per style/colour/size."""
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
        conditions.append("so.customer_name = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    where = " AND ".join(conditions)

    return frappe.db.sql(f"""
        SELECT
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
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """, params, as_dict=True)


def get_cumulative_map(filters):
    """Total KNITTING output up to and including selected date, per style/colour/size."""
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
        conditions.append("so.customer_name = %(buyer)s")
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

    # ── Aggregate at buyer level ───────────────────────────────────────────
    # agg keyed by (buyer, season)
    agg = defaultdict(lambda: {
        "styles":            set(),
        "order_qty":         0,
        "planned_qty":       0,
        "today_output":      0,
        "cumulative_output": 0,
        "planned_weight":    0.0,
        "actual_weight":     0.0,
    })

    all_keys = set(order_map.keys()) | {(l.style, l.colour, l.size) for l in daily_logs}

    for key in all_keys:
        style, colour, size = key

        order_info = order_map.get(key)
        buyer  = order_info.buyer  if order_info else ""
        season = order_info.season if order_info else ""

        bk = (buyer, season)
        bucket = agg[bk]

        if order_info:
            bucket["styles"].add(style)
            bucket["order_qty"]   += int(order_info.order_qty)
            bucket["planned_qty"] += int(order_info.planned_qty or 0)

        log = next(
            (l for l in daily_logs if l.style == style and l.colour == colour and l.size == size),
            None,
        )
        if log:
            today_out  = int(log.today_output or 0)
            actual_wt  = float(log.actual_weight or 0)
            unit_plnd  = float(log.unit_planned_weight or 0)
            planned_wt = round(today_out * unit_plnd, 3)

            bucket["today_output"]   += today_out
            bucket["actual_weight"]  += actual_wt
            bucket["planned_weight"] += planned_wt

        bucket["cumulative_output"] += cumulative_map.get(key, 0)

    # ── Build result rows ──────────────────────────────────────────────────
    result = []

    sorted_keys = sorted(agg.keys(), key=lambda k: (k[0] or "", k[1] or ""))

    for buyer, season in sorted_keys:
        b = agg[(buyer, season)]

        order_qty         = b["order_qty"]
        planned_qty       = b["planned_qty"]
        today_output      = b["today_output"]
        cumulative_output = b["cumulative_output"]
        planned_weight    = round(b["planned_weight"], 3)
        actual_weight     = round(b["actual_weight"], 3)
        variance          = round(planned_weight - actual_weight, 3)
        style_count       = len(b["styles"])

        # Balance Qty = Planned Qty − Cumulative Output
        balance_qty = planned_qty - cumulative_output

        # Completed % = (Cumulative Output / Planned Qty) × 100
        completed_pct = round((cumulative_output / order_qty) * 100, 1) if order_qty else 0.0
        completed_pct_str = f"{completed_pct:.1f}%"

        yield_pct = round((actual_weight / planned_weight) * 100, 1) if planned_weight else 0.0
        yield_pct_str = f"{yield_pct:.1f}%"

        result.append({
            "row_num":           len(result) + 1,
            "buyer":             buyer,
            "season":            season,
            "style_count":       style_count,
            "order_qty":         order_qty,
            "planned_qty":       planned_qty,
            "today_output":      today_output,
            "cumulative_output": cumulative_output,
            "balance_qty":       balance_qty,
            "completed_pct":     completed_pct_str,
            "planned_weight":    planned_weight,
            "actual_weight":     actual_weight,
            "variance":          variance,
            "yield_pct":         yield_pct_str,
        })

    # # ── Grand totals row ───────────────────────────────────────────────────
    # if result:
    #     total_styles     = sum(r["style_count"]        for r in result)
    #     total_order      = sum(r["order_qty"]          for r in result)
    #     total_planned    = sum(r["planned_qty"]        for r in result)
    #     total_today      = sum(r["today_output"]       for r in result)
    #     total_cumulative = sum(r["cumulative_output"]  for r in result)
    #     total_balance    = sum(r["balance_qty"]        for r in result)
    #     total_plnd_wt    = round(sum(r["planned_weight"]  for r in result), 3)
    #     total_actual_wt  = round(sum(r["actual_weight"]   for r in result), 3)
    #     total_variance   = round(total_plnd_wt - total_actual_wt, 3)
    #     avg_yield        = round((total_actual_wt / total_plnd_wt) * 100, 1) if total_plnd_wt else 0.0
    #     total_completed  = round((total_cumulative / total_order) * 100, 1) if total_order else 0.0

    #     result.append({
    #         "row_num":           "",
    #         "buyer":             "TOTAL / AVERAGE",
    #         "season":            "",
    #         "style_count":       total_styles,
    #         "order_qty":         total_order,
    #         "planned_qty":       total_planned,
    #         "today_output":      total_today,
    #         "cumulative_output": total_cumulative,
    #         "balance_qty":       total_balance,
    #         "completed_pct":     f"{total_completed:.1f}%",
    #         "planned_weight":    total_plnd_wt,
    #         "actual_weight":     total_actual_wt,
    #         "variance":          total_variance,
    #         "yield_pct":         f"{avg_yield:.1f}%",
    #     })

    return result