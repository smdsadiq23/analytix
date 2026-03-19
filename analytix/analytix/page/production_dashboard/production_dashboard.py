# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict
from frappe.utils import formatdate

# Physical cell display names (pc.cell_name) in pipeline order
CELL_ORDER = [
    "KNITTING",
    "MENDING",
    "WASHING",
    "CUTTING",
    "LINKING",
    "SEWING",
    "EMBROIDERY",
    "PRODUCTION",
    "PRESSING",
    "FINAL CHECK",
    "PACKING",
]


@frappe.whitelist()
def get_dashboard_data():
    order_map = _get_order_map()
    if not order_map:
        return []

    # Two separate maps:
    #   cell_in_map  — qty that completed the FIRST operation of each cell
    #   cell_out_map — qty that completed the LAST operation of each cell
    # For a single-operation cell, first = last so both maps return the same qty.
    cell_in_map   = _get_cell_op_map(op_type="first")
    cell_out_map  = _get_cell_op_map(op_type="last")

    # Earliest scan_time per (style, colour, size) — used for sorting
    scan_time_map = _get_min_scan_time_map()

    # ── Aggregate at (buyer, season, style, colour) across all sizes ──────
    agg = defaultdict(lambda: {
        "order_qty":     0,
        "planned_qty":   0,
        "delivery_date": None,
        "min_scan_time": None,          # earliest isl.scan_time across sizes
        "cell_in":       defaultdict(int),
        "cell_out":      defaultdict(int),
    })

    for (style, colour, size), info in order_map.items():
        key = (info.buyer or "", info.season or "", style, colour)
        agg[key]["order_qty"]   += int(info.order_qty or 0)
        agg[key]["planned_qty"] += int(info.planned_qty or 0)

        d = info.delivery_date
        if d and (agg[key]["delivery_date"] is None or d > agg[key]["delivery_date"]):
            agg[key]["delivery_date"] = d

        # Track the earliest scan_time seen for this (style, colour) group
        st = scan_time_map.get((style, colour, size))
        if st and (agg[key]["min_scan_time"] is None or st < agg[key]["min_scan_time"]):
            agg[key]["min_scan_time"] = st

        for cell in CELL_ORDER:
            agg[key]["cell_in"][cell]  += cell_in_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out"][cell] += cell_out_map.get((style, colour, size, cell), 0)

    # ── Build result rows ─────────────────────────────────────────────────
    result = []

    # Sort by earliest scan_time ascending (styles with the least/oldest scan
    # time appear first).  Styles that have no scans at all fall to the end.
    sorted_keys = sorted(
        agg.keys(),
        key=lambda k: (
            agg[k]["min_scan_time"] is None,          # None → pushed to end
            agg[k]["min_scan_time"] or "0000-00-00 00:00:00",
        )
    )

    for buyer, season, style, colour in sorted_keys:
        b = agg[(buyer, season, style, colour)]

        order_qty   = b["order_qty"]
        planned_qty = b["planned_qty"]

        # Build per-cell data:
        #   IN  = qty that completed the first operation of the cell
        #   OUT = qty that completed the last operation of the cell
        #   %   = OUT / ORDER QTY × 100  (not OUT/IN)
        #
        # If a cell has only one operation, first = last → IN = OUT.
        cells = {}
        for cell in CELL_ORDER:
            cell_in  = b["cell_in"].get(cell, 0)
            cell_out = b["cell_out"].get(cell, 0)
            pct      = round((cell_out / order_qty) * 100) if order_qty else 0

            cells[cell] = {
                "in":  cell_in,
                "out": cell_out,
                "pct": pct,
            }

        # OVERALL COMPLETION = PACKING OUT / ORDER QTY × 100
        packing_out    = cells["PACKING"]["out"]
        completion_pct = round((packing_out / order_qty) * 100, 1) if order_qty else 0.0

        delivery_date = ""
        if b["delivery_date"]:
            delivery_date = formatdate(b["delivery_date"], "dd-mm-yyyy")

        # ── VALIDATION: Exclude rows where PACKING completion >= 105% ─────
        if completion_pct >= 105:
            continue  # Skip this row — order is over-completed

        # ── VALIDATION: Exclude rows where KNITTING IN is 0 ──────────────
        if cells["KNITTING"]["in"] == 0:
            continue  # Skip this row — knitting has not started
        # ─────────────────────────────────────────────────────────────────

        result.append({
            "style":          style,
            "buyer":          buyer,
            "colour":         colour,
            "season":         season,
            "delivery_date":  delivery_date,
            "order_qty":      order_qty,
            "planned_qty":    planned_qty,
            "cells":          cells,
            "completion_pct": completion_pct,
        })

    return result


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_order_map():
    rows = frappe.db.sql("""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            so.custom_brand                             AS buyer,
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
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size,
                 so.custom_brand, so.delivery_date, stm.custom_season
    """, as_dict=True)
    return {(r.style, r.colour, r.size): r for r in rows}


def _get_min_scan_time_map():
    """
    Returns the earliest isl.scan_time per (style, colour, size).
    Used to sort styles so the one with the least (oldest) scan_time
    appears at the top of the dashboard.
    """
    rows = frappe.db.sql("""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            MIN(isl.scan_time)       AS min_scan_time
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi      ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor      ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc                                   ON tbc.parent = tor.name
                                               AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                ON itm.name = tor.item
        WHERE isl.log_status = 'Completed'
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """, as_dict=True)
    return {(r.style, r.colour, r.size): r.min_scan_time for r in rows}


def _get_cell_op_map(op_type="last"):
    """
    Returns qty per (style, colour, size, cell_name) for either
    the first or last operation of each physical cell.

    op_type = "first"  →  isl.operation = pcflo.first_operation  →  cell IN
    op_type = "last"   →  isl.operation = pcflo.last_operation   →  cell OUT

    For a single-operation cell, first_operation = last_operation,
    so both calls return identical quantities for that cell.

    pcflo join uses AND pcflo.physical_cell = pc.name to pin each
    scan to exactly its own cell row — prevents double-counting
    across the child table rows.
    """
    op_field  = "first_operation" if op_type == "first" else "last_operation"
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            pc.cell_name                                AS cell_name,
            COALESCE(SUM(pi.quantity), 0)               AS qty
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
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component
                                                   AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                   ON pcflo.parent = tbc.work_order
                                                   AND pcflo.physical_cell = pc.name
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE isl.operation = pcflo.{op_field}
          AND isl.log_status = 'Completed'
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): int(r.qty) for r in rows}