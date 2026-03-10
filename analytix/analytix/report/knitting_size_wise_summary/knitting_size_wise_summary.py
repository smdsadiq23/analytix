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
        {"label": "Buyer",              "fieldname": "buyer",               "fieldtype": "Data",    "width": 150},
        {"label": "Season",             "fieldname": "season",              "fieldtype": "Data",    "width": 100},
        {"label": "Delivery Date",      "fieldname": "delivery_date",       "fieldtype": "Data",    "width": 120},
        {"label": "Style",              "fieldname": "style",               "fieldtype": "Data",    "width": 140},
        {"label": "Colour",             "fieldname": "colour",              "fieldtype": "Data",    "width": 120},
        {"label": "Size",               "fieldname": "size",                "fieldtype": "Data",    "width": 60},
        {"label": "Order Qty",          "fieldname": "order_qty",           "fieldtype": "Int",     "width": 100},
        {"label": "Planned Qty",        "fieldname": "planned_qty",         "fieldtype": "Int",     "width": 100},
        {"label": "Total Output",       "fieldname": "today_output",        "fieldtype": "Int",     "width": 110},
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

    if filters.get("season"):
        conditions.append("stm.custom_season = %(season)s")
        params["season"] = filters["season"]

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


def get_total_production(filters):
    """
    All KNITTING OUT completed entries — no date restriction.
    Grouped by style / colour / size (aggregate across all dates).
    Also fetches unit_planned_weight from Work Order Line Item.
    """
    conditions = [
        "pc.cell_name = 'KNITTING'",
        "isl.operation = 'KNITTING OUT'",
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Pass')",
    ]
    params = {}

    if filters.get("buyer"):
        conditions.append("so.customer = %(buyer)s")
        params["buyer"] = filters["buyer"]

    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
        params["style"] = filters["style"]

    if filters.get("season"):
        conditions.append("stm.custom_season = %(season)s")
        params["season"] = filters["season"]

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
        INNER JOIN `tabStyle Master` stm            ON stm.name = itm.custom_style_master
        WHERE {where}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
        ORDER BY itm.custom_style_master, tbc.size
    """, params, as_dict=True)


def get_data(filters):
    order_map   = get_order_map(filters)
    total_logs  = get_total_production(filters)

    result = []

    for log in total_logs:
        key = (log.style, log.colour, log.size)

        order_info        = order_map.get(key)
        order_qty         = int(order_info.order_qty)   if order_info else 0
        planned_qty       = int(order_info.planned_qty)  if order_info else 0

        today_output      = int(log.today_output or 0)
        # Without a date filter cumulative == total output
        cumulative_output = today_output
        actual_weight     = round(float(log.actual_weight or 0), 3)

        # Planned weight = total output qty × per-unit planned weight
        unit_plnd      = float(log.unit_planned_weight or 0)
        planned_weight = round(today_output * unit_plnd, 3)

        # Balance Qty = Planned Qty − Cumulative Output
        balance_qty = planned_qty - cumulative_output

        # Completed % = (Cumulative Output / Order Qty) × 100
        completed_pct     = round((cumulative_output / order_qty) * 100, 1) if order_qty else 0.0
        completed_pct_str = f"{completed_pct:.1f}%"

        # Yield % = (Planned Wt / Actual Wt) × 100  — > 100% means over-consumed
        yield_pct     = round((planned_weight / actual_weight) * 100, 2) if actual_weight else 0.0
        yield_pct_str = f"{yield_pct:.1f}%"

        # Wastage/Excess: positive = saved (good), negative = over-used (bad)
        wastage_excess     = round(((actual_weight - planned_weight) / planned_weight) * 100, 2) if planned_weight else 0.0
        wastage_excess_str = f"{wastage_excess:+.1f}%"

        # Format delivery date
        delivery_date = ""
        if order_info and order_info.delivery_date:
            delivery_date = formatdate(order_info.delivery_date, "dd-mm-yyyy")

        result.append({
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

    return result