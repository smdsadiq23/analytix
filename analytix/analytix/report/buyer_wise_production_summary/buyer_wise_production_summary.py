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
        {"label": "Buyer",              "fieldname": "buyer",               "fieldtype": "Data",    "width": 190},
        {"label": "Season",             "fieldname": "season",              "fieldtype": "Data",    "width": 100},
        {"label": "No. of Styles",      "fieldname": "style_count",         "fieldtype": "Int",     "width": 110},
        {"label": "Order Qty",          "fieldname": "order_qty",           "fieldtype": "Int",     "width": 100},
        {"label": "Planned Qty",        "fieldname": "planned_qty",         "fieldtype": "Int",     "width": 100},
        {"label": "Today Output",       "fieldname": "today_output",        "fieldtype": "Int",     "width": 110},
        {"label": "Cumulative Output",  "fieldname": "cumulative_qty",      "fieldtype": "Int",     "width": 140},
        {"label": "Completed %",        "fieldname": "completed_pct",       "fieldtype": "Data",    "width": 110},
        {"label": "Balance Qty",        "fieldname": "balance_qty",         "fieldtype": "Int",     "width": 110},
        {"label": "Rejection",          "fieldname": "rejection",           "fieldtype": "Int",     "width": 110},
    ]


def get_order_rows(filters):
    """
    Returns list of rows — one per (style, colour, size, buyer, season, work_order).
    Keying by work_order allows scoping cumulative/daily production correctly.
    """
    conditions = []
    params     = {}

    if filters.get("buyer"):
        conditions.append("so.custom_brand = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    where = " AND ".join(conditions) if conditions else "1=1"

    return frappe.db.sql(f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            tbc.work_order                              AS work_order,
            so.custom_brand                             AS buyer,
            stm.custom_season                           AS season,
            COALESCE(SUM(soi.custom_order_qty), 0)      AS order_qty,
            COALESCE(SUM(soi.qty), 0)                   AS planned_qty
        FROM (
            SELECT DISTINCT sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
        INNER JOIN `tabSales Order` so          ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi    ON soi.parent = so.name AND soi.custom_size = tbc.size
        INNER JOIN `tabItem` itm                ON itm.name = soi.item_code
        INNER JOIN `tabStyle Master` stm        ON stm.name = itm.custom_style_master
        WHERE {where}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size,
                 tbc.work_order, so.custom_brand, stm.custom_season
    """, params, as_dict=True)


def get_daily_map(filters):
    """
    Today's output per (style, colour, size, work_order).
    Scoped to the selected date only, across all departments.
    """
    conditions = []
    params     = {}

    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) = %(date)s")
        params["date"] = filters["date"]

    if filters.get("buyer"):
        conditions.append("so.custom_brand = %(buyer)s")
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
            tbc.work_order                              AS work_order,
            COALESCE(SUM(pi.quantity), 0)               AS today_output
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
            ON tbc.parent = tor.name AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabWork Order` wo
            ON wo.name = tbc.work_order
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE isl.operation = wo.custom_last_operation
            AND isl.log_status = 'Completed'
            AND (
                isl.status IN ('Counted', 'Activated', 'Pass')
                OR (isl.status = 'Unlink Link' AND pi.status <> 'Unlink Link Scrap')
            )
            AND {where}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, tbc.work_order
    """, params, as_dict=True)

    return {(r.style, r.colour, r.size, r.work_order): int(r.today_output) for r in rows}


def get_cumulative_map(filters):
    """
    Cumulative output up to and including the selected date,
    per (style, colour, size, work_order) — scoped per work order to avoid
    cross-season double counting.
    """
    conditions = []
    params     = {}

    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) <= %(date)s")
        params["date"] = filters["date"]

    if filters.get("buyer"):
        conditions.append("so.custom_brand = %(buyer)s")
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
            tbc.work_order                              AS work_order,
            COALESCE(SUM(pi.quantity), 0)               AS cumulative_qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
            ON tbc.parent = tor.name AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabWork Order` wo
            ON wo.name = tbc.work_order
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE isl.operation = wo.custom_last_operation
            AND isl.log_status = 'Completed'
            AND (
                isl.status IN ('Counted', 'Activated', 'Pass')
                OR (isl.status = 'Unlink Link' AND pi.status <> 'Unlink Link Scrap')
            )
            AND {where}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, tbc.work_order
    """, params, as_dict=True)

    return {(r.style, r.colour, r.size, r.work_order): int(r.cumulative_qty) for r in rows}


def get_rejection_map(filters):
    """
    Total rejected quantity per (style, colour, size, work_order),
    where isl.status IN ('QC Rejected', 'SP Rejected').
    No date scoping — cumulative rejections for the order.
    Pass date filter via filters["date"] to scope to a specific day if needed.
    """
    conditions = []
    params     = {}

    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) <= %(date)s")
        params["date"] = filters["date"]

    if filters.get("buyer"):
        conditions.append("so.custom_brand = %(buyer)s")
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
            tbc.work_order                              AS work_order,
            COALESCE(SUM(pi.quantity), 0)               AS rejection
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
            ON tbc.parent = tor.name AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabWork Order` wo
            ON wo.name = tbc.work_order
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE isl.status IN ('QC Rejected', 'SP Rejected')
            AND {where}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, tbc.work_order
    """, params, as_dict=True)

    return {(r.style, r.colour, r.size, r.work_order): int(r.rejection) for r in rows}


def get_data(filters):
    order_rows     = get_order_rows(filters)
    if not order_rows:
        return []

    daily_map      = get_daily_map(filters)
    cumulative_map = get_cumulative_map(filters)
    rejection_map  = get_rejection_map(filters)

    # ── Aggregate at (buyer, season) level ────────────────────────────────
    # Key includes work_order so cumulative/daily are scoped correctly per
    # work order — prevents cross-season double counting.
    agg = defaultdict(lambda: {
        "styles":         set(),
        "order_qty":      0,
        "planned_qty":    0,
        "today_output":   0,
        "cumulative_qty": 0,
        "rejection":      0,
    })

    for row in order_rows:
        key    = (row.buyer or "", row.season or "")
        wo_key = (row.style, row.colour, row.size, row.work_order)

        agg[key]["styles"].add(row.style)
        agg[key]["order_qty"]      += int(row.order_qty)
        agg[key]["planned_qty"]    += int(row.planned_qty or 0)
        agg[key]["today_output"]   += daily_map.get(wo_key, 0)
        agg[key]["cumulative_qty"] += cumulative_map.get(wo_key, 0)
        agg[key]["rejection"]      += rejection_map.get(wo_key, 0)

    # ── Build result rows — sort by buyer, season ──────────────────────────
    result = []

    sorted_keys = sorted(agg.keys(), key=lambda k: (k[0], k[1]))

    for buyer, season in sorted_keys:
        b = agg[(buyer, season)]

        order_qty      = b["order_qty"]
        planned_qty    = b["planned_qty"]
        today_output   = b["today_output"]
        cumulative_qty = b["cumulative_qty"]
        rejection      = b["rejection"]
        style_count    = len(b["styles"])

        completed_pct     = round((cumulative_qty / order_qty) * 100, 1) if order_qty else 0.0
        completed_pct_str = f"{completed_pct:.1f}%"

        balance_qty = planned_qty - cumulative_qty

        result.append({
            "buyer":          buyer,
            "season":         season,
            "style_count":    style_count,
            "order_qty":      order_qty,
            "planned_qty":    planned_qty,
            "today_output":   today_output,
            "cumulative_qty": cumulative_qty,
            "completed_pct":  completed_pct_str,
            "balance_qty":    balance_qty,
            "rejection":      rejection,
        })

    # # ── TOTAL / AVERAGE row ────────────────────────────────────────────────
    # if result:
    #     total_styles     = sum(r["style_count"]    for r in result)
    #     total_order      = sum(r["order_qty"]      for r in result)
    #     total_planned    = sum(r["planned_qty"]     for r in result)
    #     total_today      = sum(r["today_output"]    for r in result)
    #     total_cumulative = sum(r["cumulative_qty"]  for r in result)
    #     total_balance    = sum(r["balance_qty"]     for r in result)
    #     total_rejection  = sum(r["rejection"]       for r in result)
    #     total_pct        = round((total_cumulative / total_order) * 100, 1) if total_order else 0.0

    #     result.append({
    #         "row_num":        None,
    #         "buyer":          "TOTAL / AVERAGE",
    #         "season":         "",
    #         "style_count":    total_styles,
    #         "order_qty":      total_order,
    #         "planned_qty":    total_planned,
    #         "today_output":   total_today,
    #         "cumulative_qty": total_cumulative,
    #         "completed_pct":  f"{total_pct:.1f}%",
    #         "balance_qty":    total_balance,
    #         "rejection":      total_rejection,
    #     })

    return result