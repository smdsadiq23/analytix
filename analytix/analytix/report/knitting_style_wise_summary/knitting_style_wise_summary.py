# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import formatdate
from collections import defaultdict


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data    = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Style",              "fieldname": "style",               "fieldtype": "Data",    "width": 140},
        {"label": "Buyer",              "fieldname": "buyer",               "fieldtype": "Data",    "width": 150},
        {"label": "Season",             "fieldname": "season",              "fieldtype": "Data",    "width": 100},
        {"label": "Colour",             "fieldname": "colour",              "fieldtype": "Data",    "width": 120},
        {"label": "Delivery Date",      "fieldname": "delivery_date",       "fieldtype": "Data",    "width": 120},
        {"label": "Order Qty",          "fieldname": "order_qty",           "fieldtype": "Int",     "width": 100},
        {"label": "Planned Qty",        "fieldname": "planned_qty",         "fieldtype": "Int",     "width": 100},
        {"label": "Today Output",       "fieldname": "today_output",        "fieldtype": "Int",     "width": 110},
        {"label": "Cumulative Output",  "fieldname": "cumulative_output",   "fieldtype": "Int",     "width": 140},
        {"label": "Balance Qty",        "fieldname": "balance_qty",         "fieldtype": "Int",     "width": 110},
        {"label": "Completed %",        "fieldname": "completed_pct",       "fieldtype": "Data",    "width": 110},
        {"label": "Planned Wt (kg)",    "fieldname": "planned_weight",      "fieldtype": "Float",   "width": 130},
        {"label": "Actual Wt (kg)",     "fieldname": "actual_weight",       "fieldtype": "Float",   "width": 130},
        {"label": "Variance (kg)",      "fieldname": "variance",            "fieldtype": "Float",   "width": 120},
        {"label": "Yield %",            "fieldname": "yield_pct",           "fieldtype": "Data",    "width": 100},
    ]


def _build_where(filters, table_aliases=None):
    """Return (conditions_list, params_dict) for common filters."""
    conditions = []
    params     = {}

    if filters.get("buyer"):
        alias = f"{table_aliases['so']}." if table_aliases else "so."
        conditions.append(f"{alias}custom_brand = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        alias = f"{table_aliases['itm']}." if table_aliases else "itm."
        conditions.append(f"{alias}custom_style_master = %(style)s")
        params["style"] = filters["style"]

    return conditions, params


def get_order_map(filters):
    """
    Order qty per (style, colour, size) → also carries buyer / season.
    Returns dict keyed by (style, colour, size).
    """
    conditions, params = _build_where(filters)
    where = " AND ".join(conditions) if conditions else "1=1"

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            so.custom_brand                            AS buyer,
            so.delivery_date                            AS delivery_date,
            stm.custom_season                           AS season,
            COALESCE(SUM(soi.custom_order_qty), 0)      AS order_qty,
            COALESCE(SUM(soi.qty), 0)                   AS planned_qty
        FROM (
            SELECT DISTINCT sales_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
        INNER JOIN `tabSales Order` so          ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi    ON soi.parent = so.name AND soi.custom_size = tbc.size        
        INNER JOIN `tabItem` itm                ON itm.name = soi.item_code
        INNER JOIN `tabStyle Master` stm        ON stm.name = itm.custom_style_master
        WHERE {where}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size,
                 so.custom_brand, so.delivery_date, stm.custom_season
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
        conditions.append("so.custom_brand = %(buyer)s")
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
        conditions.append("so.custom_brand = %(buyer)s")
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

    # ── Aggregate everything at (style, colour) level ──────────────────────
    # Accumulator keyed by (style, colour)
    agg = defaultdict(lambda: {
        "buyer":             "",
        "season":            "",
        "order_qty":         0,
        "planned_qty":       0,
        "today_output":      0,
        "cumulative_output": 0,
        "planned_weight":    0.0,
        "actual_weight":     0.0,
        "delivery_date":     None,
    })

    # Collect all (style, colour, size) keys that have either production or orders
    all_keys = set(order_map.keys()) | {(l.style, l.colour, l.size) for l in daily_logs}

    for key in all_keys:
        style, colour, size = key
        sc_key = (style, colour)
        bucket = agg[sc_key]

        order_info = order_map.get(key)
        if order_info:
            bucket["buyer"]       = order_info.buyer
            bucket["season"]      = order_info.season
            bucket["order_qty"]   += int(order_info.order_qty)
            bucket["planned_qty"] += int(order_info.planned_qty or 0)
            d = order_info.delivery_date
            if d and (bucket["delivery_date"] is None or d > bucket["delivery_date"]):
                bucket["delivery_date"] = d

        # Find matching daily log for this size
        log = next((l for l in daily_logs if l.style == style and l.colour == colour and l.size == size), None)
        if log:
            today_out    = int(log.today_output or 0)
            actual_wt    = float(log.actual_weight or 0)
            unit_plnd    = float(log.unit_planned_weight or 0)
            planned_wt   = round(today_out * unit_plnd, 3)

            bucket["today_output"]      += today_out
            bucket["actual_weight"]     += actual_wt
            bucket["planned_weight"]    += planned_wt

        bucket["cumulative_output"] += cumulative_map.get(key, 0)

    # ── Build result rows ──────────────────────────────────────────────────
    result = []

    # Sort: delivery date descending, None last
    sorted_keys = sorted(
        agg.keys(),
        key=lambda k: agg[k]["delivery_date"].isoformat() if agg[k]["delivery_date"] else "0000-00-00",
        reverse=True,
    )

    for style, colour in sorted_keys:
        b = agg[(style, colour)]

        order_qty         = b["order_qty"]
        planned_qty       = b["planned_qty"]
        today_output      = b["today_output"]
        cumulative_output = b["cumulative_output"]
        planned_weight    = round(b["planned_weight"], 3)
        actual_weight     = round(b["actual_weight"], 3)
        variance          = round(planned_weight - actual_weight, 3)

        # Balance Qty = Planned Qty − Cumulative Output
        balance_qty = planned_qty - cumulative_output

        # Completed % = (Cumulative Output / Planned Qty) × 100
        completed_pct = round((cumulative_output / order_qty) * 100, 1) if order_qty else 0.0
        completed_pct_str = f"{completed_pct:.1f}%"

        # Yield % = (Actual / Planned) × 100
        yield_pct = round((planned_weight / actual_weight) * 100, 1) if actual_weight else 0.0
        yield_pct_str = f"{yield_pct:.1f}%"

        delivery_date = ""
        if b["delivery_date"]:
            delivery_date = formatdate(b["delivery_date"], "dd-mm-yyyy")

        result.append({
            "style":             style,
            "buyer":             b["buyer"],
            "season":            b["season"],
            "colour":            colour,
            "delivery_date":     delivery_date,
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

    # # ── Summary / totals row ───────────────────────────────────────────────
    # if result:
    #     total_order      = sum(r["order_qty"]         for r in result)
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
    #         "row_num":           None,
    #         "style":             "TOTAL / AVERAGE",
    #         "buyer":             "",
    #         "season":            "",
    #         "colour":            "",
    #         "delivery_date":     "",
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