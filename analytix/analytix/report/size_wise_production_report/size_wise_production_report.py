# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt
# size_wise_production_report.py

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
        {"label": "Department",    "fieldname": "department",        "fieldtype": "Data", "width": 130},
        {"label": "Buyer",         "fieldname": "buyer",             "fieldtype": "Data", "width": 150},
        {"label": "Season",        "fieldname": "season",            "fieldtype": "Data", "width": 100},
        {"label": "Delivery Date", "fieldname": "delivery_date",     "fieldtype": "Data", "width": 130},
        {"label": "Style",         "fieldname": "style",             "fieldtype": "Data", "width": 140},
        {"label": "Colour",        "fieldname": "colour",            "fieldtype": "Data", "width": 120},
        {"label": "Size",          "fieldname": "size",              "fieldtype": "Data", "width": 80},
        {"label": "Order Qty",     "fieldname": "order_qty",         "fieldtype": "Int",  "width": 100},
        {"label": "Planned Qty",   "fieldname": "planned_qty",       "fieldtype": "Int",  "width": 100},
        {"label": "Completed Qty", "fieldname": "completed_qty",     "fieldtype": "Int",  "width": 130},
        {"label": "Balance Qty",   "fieldname": "balance_qty",       "fieldtype": "Int",  "width": 110},
        {"label": "Completed %",   "fieldname": "completed_percent", "fieldtype": "Data", "width": 120},
        {"label": "Rejection",     "fieldname": "rejection",         "fieldtype": "Int",  "width": 110},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_conditions(filters, aliases):
    """
    Build a WHERE snippet + params dict from filters.

    aliases = dict mapping filter key → qualified column expression, e.g.
        {"buyer": "so.custom_brand", "style": "itm.custom_style_master", ...}
    """
    conditions = []
    params     = {}
    for key, col in aliases.items():
        if filters.get(key):
            conditions.append(f"{col} = %({key})s")
            params[key] = filters[key]
    return (" AND ".join(conditions) or "1=1"), params


# ─────────────────────────────────────────────────────────────────────────────
# Query 1 — order map  (static order details)
# ─────────────────────────────────────────────────────────────────────────────

def get_order_map(filters):
    """
    Returns a dict keyed by (style, colour, size) → order row.

    Optimisation over original:
    • Replaced the correlated DISTINCT subquery on tabTracking Order Bundle
      Configuration with a plain GROUP BY — MySQL can satisfy this with a
      single pass and the composite index on (parent, sales_order, size).
    • Single aggregation pass; no nested SELECT.
    """
    where, params = _build_conditions(filters, {
        "buyer": "so.custom_brand",
        "style": "itm.custom_style_master",
    })

    query = f"""
        SELECT
            itm.custom_style_master                AS style,
            itm.custom_colour_name                 AS colour,
            tbc.size                               AS size,
            so.custom_brand                        AS buyer,
            so.delivery_date                       AS delivery_date,
            stm.custom_season                      AS season,
            COALESCE(SUM(soi.custom_order_qty), 0) AS order_qty,
            COALESCE(SUM(soi.qty), 0)              AS planned_qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabSales Order`      so  ON so.name  = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
                                             AND soi.custom_size = tbc.size
        INNER JOIN `tabItem`             itm ON itm.name = soi.item_code
        INNER JOIN `tabStyle Master`     stm ON stm.name = itm.custom_style_master
        WHERE tbc.parentfield = 'bundle_configurations'
          AND {where}
        GROUP BY
            itm.custom_style_master,
            itm.custom_colour_name,
            tbc.size,
            so.custom_brand,
            so.delivery_date,
            stm.custom_season
    """

    rows = frappe.db.sql(query, params, as_dict=True)
    return {(r.style, r.colour, r.size): r for r in rows}


# ─────────────────────────────────────────────────────────────────────────────
# Query 2 — combined completed + rejection in ONE pass
# ─────────────────────────────────────────────────────────────────────────────

def get_production_and_rejection(filters):
    """
    Replaces the two separate queries (get_production_data + get_rejection_map)
    with a single query that uses conditional aggregation.

    • completed_qty  = SUM where status is a "good" completion
    • rejection      = SUM where status is a rejection

    Optimisation over original:
    • One DB round-trip instead of two.
    • The DISTINCT subquery on tbc is replaced by GROUP BY — same result,
      avoids a temporary table.
    • The pcflo JOIN for last_operation is kept only for the completed branch
      via a CASE expression so rejected rows don't need it (moved to a
      separate filtered arm).  Because both conditions share the same FROM /
      JOIN graph we keep all joins and split via CASE inside SUM().
    """
    where, params = _build_conditions(filters, {
        "department": "pc.name",
        "buyer":      "so.custom_brand",
        "style":      "itm.custom_style_master",
    })

    query = f"""
        SELECT
            pc.cell_name               AS department,
            itm.custom_style_master    AS style,
            itm.custom_colour_name     AS colour,
            tbc.size                   AS size,

            /* completed: last-operation scans that passed */
            COALESCE(SUM(
                CASE
                    WHEN isl.operation = pcflo.last_operation
                     AND isl.log_status = 'Completed'
                     AND (
                           isl.status IN ('Counted','Activated','Pass')
                           OR (isl.status = 'Unlink Link'
                               AND pi.status = 'Unlink Link Scrap')
                         )
                    THEN pi.quantity
                    ELSE 0
                END
            ), 0) AS completed_qty,

            /* rejection: any scan flagged as rejected */
            COALESCE(SUM(
                CASE
                    WHEN isl.status IN ('QC Rejected','SP Rejected')
                    THEN pi.quantity
                    ELSE 0
                END
            ), 0) AS rejection

        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item`  pi   ON pi.name  = isl.production_item
        INNER JOIN `tabTracking Order`   tor  ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
               ON tbc.parent = tor.name
              AND tbc.size   = pi.size
              AND tbc.parentfield = 'bundle_configurations'
        INNER JOIN `tabItem`             itm  ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell`    pc   ON pc.name  = isl.physical_cell
        INNER JOIN `tabTracking Component` tc ON tc.name  = pi.component
                                             AND tc.is_main = 1
        /* LEFT JOIN so rejections (which have no last_operation requirement) still show */
        LEFT JOIN `tabPhysical Cell First and Last Operation` pcflo
               ON pcflo.parent = tbc.work_order
        INNER JOIN `tabSales Order`      so   ON so.name  = tbc.sales_order
        WHERE {where}
        GROUP BY
            pc.cell_name,
            itm.custom_style_master,
            itm.custom_colour_name,
            tbc.size
        ORDER BY
            pc.cell_name,
            itm.custom_style_master,
            tbc.size
    """

    rows = frappe.db.sql(query, params, as_dict=True)

    # Split into the two structures the assembler expects
    prod_index    = {}   # (style, colour, size) → [dept rows]
    rejection_map = {}   # (dept, style, colour, size) → int

    for r in rows:
        key      = (r.style, r.colour, r.size)
        rej_key  = (r.department, r.style, r.colour, r.size)

        prod_index.setdefault(key, []).append(r)
        rejection_map[rej_key] = int(r.rejection)

    return prod_index, rejection_map


# ─────────────────────────────────────────────────────────────────────────────
# Assembler
# ─────────────────────────────────────────────────────────────────────────────

def get_data(filters):
    order_map = get_order_map(filters)
    if not order_map:
        return []

    prod_index, rejection_map = get_production_and_rejection(filters)

    result = []

    for key, order_info in order_map.items():
        order_qty   = int(order_info.order_qty)
        planned_qty = int(order_info.planned_qty or 0)

        delivery_date = (
            formatdate(order_info.delivery_date, "dd-mm-yyyy")
            if order_info.delivery_date else ""
        )

        dept_logs = prod_index.get(key)

        if not dept_logs:
            result.append({
                "delivery_date":      delivery_date,
                "_dd_raw":            order_info.delivery_date,
                "department":         "",
                "buyer":              order_info.buyer,
                "season":             order_info.season,
                "style":              key[0],
                "colour":             key[1],
                "size":               key[2],
                "order_qty":          order_qty,
                "planned_qty":        planned_qty,
                "completed_qty":      0,
                "balance_qty":        planned_qty,
                "completed_percent":  "0.0%",
                "rejection":          0,
            })
        else:
            for log in dept_logs:
                completed_qty = int(log.completed_qty)
                balance_qty   = planned_qty - completed_qty
                completed_pct = (
                    round((completed_qty / order_qty) * 100, 1)
                    if order_qty > 0 else 0.0
                )
                rej_key   = (log.department, key[0], key[1], key[2])
                rejection = rejection_map.get(rej_key, 0)

                result.append({
                    "delivery_date":      delivery_date,
                    "_dd_raw":            order_info.delivery_date,
                    "department":         log.department,
                    "buyer":              order_info.buyer,
                    "season":             order_info.season,
                    "style":              key[0],
                    "colour":             key[1],
                    "size":               key[2],
                    "order_qty":          order_qty,
                    "planned_qty":        planned_qty,
                    "completed_qty":      completed_qty,
                    "balance_qty":        balance_qty,
                    "completed_percent":  f"{completed_pct:.1f}%",
                    "rejection":          rejection,
                })

    # Sort by delivery date descending, nulls last
    result.sort(
        key=lambda r: str(r["_dd_raw"] or "0000-00-00"),
        reverse=True,
    )
    for r in result:
        r.pop("_dd_raw", None)

    return result