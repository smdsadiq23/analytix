# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt
#
# Owner Dashboard — backend
#
# WHY GLOBAL AGGREGATION IS WRONG
# ================================
# Previous versions computed WIP / pending_in on globally-summed cum_in and
# cum_out values.  This produces wrong results whenever a cell (e.g. EMBROIDERY)
# is applicable for some styles but not others:
#
#   Style A (EMBROIDERY applicable):
#     SEWING.cum_out=1000, EMBROIDERY.cum_out=800, PRODUCTION.cum_in=650
#     → PRODUCTION.pending_in = 800 - 650 = 150
#
#   Style B (EMBROIDERY NOT applicable → patched cum_out = SEWING.cum_out):
#     SEWING.cum_out=500, PRODUCTION.cum_in=460
#     → PRODUCTION.pending_in = 500 - 460 = 40   (predecessor = SEWING, skipping EMBROIDERY)
#
#   Per-style sum: pending_in = 190  ✓
#
#   Global approach (EMBROIDERY IS in applicable_set because Style A uses it,
#   so no patch; global EMBROIDERY.cum_out = 800 only covers Style A):
#     PRODUCTION.pending_in = 800 - (650+460) = -310 → 0  ✗
#
# THE FIX
# ========
# Compute per (style, colour, size) — exactly as shopfloor_performance does —
# then SUM.  The SQL queries return per-SKU rows; Python applies the same
# applicable_cells + predecessor walk + max(0,...) clamping per SKU, then
# aggregates.  This matches the shopfloor to the unit.

import frappe
from collections import defaultdict
from datetime import date as _date

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

CELL_LIST_SQL = ", ".join(f"'{c}'" for c in CELL_ORDER)


# ── Shared scan JOIN (identical to shopfloor_performance._get_cell_op_map_for_period) ──
_SCAN_JOINS = f"""
    FROM `tabItem Scan Log` isl
    INNER JOIN `tabProduction Item` pi
        ON pi.name = isl.production_item
    INNER JOIN `tabTracking Order` tor
        ON tor.name = pi.tracking_order
    INNER JOIN (
        SELECT DISTINCT parent, sales_order, work_order, size
        FROM `tabTracking Order Bundle Configuration`
        WHERE parentfield = 'bundle_configurations'
    ) tbc ON tbc.parent = tor.name AND tbc.size = pi.size
    INNER JOIN `tabItem` itm
        ON itm.name = tor.item
    INNER JOIN `tabPhysical Cell` pc
        ON pc.name = isl.physical_cell
    INNER JOIN `tabTracking Component` tc
        ON tc.name = pi.component AND tc.is_main = 1
    INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
        ON pcflo.parent = tbc.work_order
        AND pcflo.physical_cell = pc.name
    INNER JOIN `tabSales Order` so
        ON so.name = tbc.sales_order
    WHERE isl.log_status = 'Completed'
      AND pc.cell_name IN ({CELL_LIST_SQL})
      AND (
          isl.status IN ('Counted', 'Activated', 'Pass')
          OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
      )
"""


def _op_case(op_label, field):
    return (
        f"CASE WHEN pc.cell_name = 'MENDING' THEN '{op_label}' "
        f"ELSE pcflo.{field} END"
    )


@frappe.whitelist()
def get_owner_dashboard_data(date=None):
    """
    Returns a dict keyed by cell_name:
        { cell_name: { input, output, pending_in, wip, applicable } }
    KNITTING also carries: { shift1, shift2 }

    All WIP / pending_in values are computed per (style, colour, size) and
    then summed — identical logic to shopfloor_performance.get_dashboard_data.
    """
    if not date:
        date = _date.today().isoformat()

    params = {"date": date}

    # ── Daily IN / OUT per SKU per cell (selected date) ───────────────────
    daily_in_map  = _sku_cell_map(op_type="first", date_cond="DATE(isl.logged_time) = %(date)s", params=params)
    daily_out_map = _sku_cell_map(op_type="last",  date_cond="DATE(isl.logged_time) = %(date)s", params=params)

    # ── Cumulative IN / OUT per SKU per cell (all time) ───────────────────
    cum_in_map  = _sku_cell_map(op_type="first", date_cond="1=1", params={})
    cum_out_map = _sku_cell_map(op_type="last",  date_cond="1=1", params={})

    # ── KNITTING shifts ───────────────────────────────────────────────────
    knitting_shift1     = _knitting_shift(date, shift=1)
    knitting_shift2     = _knitting_shift(date, shift=2)
    knitting_shift1_cum = _knitting_shift(None, shift=1)
    knitting_shift2_cum = _knitting_shift(None, shift=2)
    knitting_shift_cum  = _knitting_shift_sku_map(None)  # cumulative per SKU

    # ── Applicable cells per SKU (from pcflo) ────────────────────────────
    applicable_map = _get_applicable_cells_map()  # (style,colour,size) → set of cell names

    # ── Collect all SKUs ──────────────────────────────────────────────────
    all_skus = set()
    for (style, colour, size, _cell) in cum_in_map:
        all_skus.add((style, colour, size))
    for (style, colour, size, _cell) in cum_out_map:
        all_skus.add((style, colour, size))
    for (style, colour, size) in applicable_map:
        all_skus.add((style, colour, size))

    # ── Aggregate totals ──────────────────────────────────────────────────
    # Per cell: sum of daily in, daily out, pending_in, wip across all SKUs
    total_daily_in  = defaultdict(int)
    total_daily_out = defaultdict(int)
    total_pending   = defaultdict(int)
    total_wip       = defaultdict(int)

    for sku in all_skus:
        style, colour, size = sku

        # Applicable cells for this SKU (KNITTING always included)
        applicable = applicable_map.get(sku, set()) | {"KNITTING"}

        # KNITTING cumulative output for this SKU (from shift maps)
        knitting_cum_sku = knitting_shift_cum.get(sku, 0)

        # Build per-cell cum_out for this SKU, then patch non-applicable cells
        sku_cum_out = {}
        for cell in CELL_ORDER:
            if cell == "KNITTING":
                sku_cum_out[cell] = knitting_cum_sku
            else:
                sku_cum_out[cell] = cum_out_map.get((style, colour, size, cell), 0)

        # Patch non-applicable cells (mirrors shopfloor_performance patching)
        for i, cell in enumerate(CELL_ORDER):
            if i == 0 or cell in applicable:
                continue
            for j in range(i - 1, -1, -1):
                pred = CELL_ORDER[j]
                if pred in applicable or j == 0:
                    sku_cum_out[cell] = sku_cum_out.get(pred, 0)
                    break

        # Accumulate daily in / out
        for cell in CELL_ORDER:
            if cell == "KNITTING":
                continue
            total_daily_in[cell]  += daily_in_map.get((style, colour, size, cell), 0)
            total_daily_out[cell] += daily_out_map.get((style, colour, size, cell), 0)

        # Compute pending_in and wip per cell for this SKU then sum
        for i, cell in enumerate(CELL_ORDER):
            if i == 0 or cell not in applicable:
                continue

            # Nearest applicable predecessor
            prev_cum_out = 0
            for j in range(i - 1, -1, -1):
                pred = CELL_ORDER[j]
                if pred in applicable:
                    prev_cum_out = sku_cum_out.get(pred, 0)
                    break

            cur_cum_in  = cum_in_map.get((style, colour, size, cell), 0)
            cur_cum_out = sku_cum_out.get(cell, 0)

            total_pending[cell] += max(0, prev_cum_out - cur_cum_in)
            total_wip[cell]     += max(0, cur_cum_in  - cur_cum_out)

    # ── Build result dict ─────────────────────────────────────────────────
    result = {}

    for i, cell in enumerate(CELL_ORDER):
        if i == 0:
            result[cell] = {
                "input":      None,
                "output":     knitting_shift1 + knitting_shift2,
                "shift1":     knitting_shift1,
                "shift2":     knitting_shift2,
                "pending_in": None,
                "wip":        None,
                "applicable": True,
            }
            continue

        result[cell] = {
            "input":      total_daily_in.get(cell, 0),
            "output":     total_daily_out.get(cell, 0),
            "pending_in": total_pending.get(cell, 0),
            "wip":        total_wip.get(cell, 0),
            "applicable": True,  # always True for display; zero means none
        }

    return result


# ── Private helpers ───────────────────────────────────────────────────────────

def _sku_cell_map(op_type, date_cond, params):
    """
    Returns {(style, colour, size, cell_name): qty}
    Mirrors shopfloor_performance._get_cell_op_map_for_period exactly.
    """
    op_field   = "first_operation" if op_type == "first" else "last_operation"
    mending_op = "MENDING IN"      if op_type == "first" else "MENDING OUT"

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            pc.cell_name             AS cell_name,
            COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case(mending_op, op_field)}
          AND {date_cond}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, params, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): int(r.qty) for r in rows}


def _knitting_shift(date, shift):
    """
    Total KNITTING output for shift 1 (10:00–20:00) or shift 2 (20:00–10:00).
    date=None → all-time cumulative.
    """
    time_cond = (
        "TIME(isl.logged_time) >= '10:00:00' AND TIME(isl.logged_time) < '20:00:00'"
        if shift == 1
        else "(TIME(isl.logged_time) >= '20:00:00' OR TIME(isl.logged_time) < '10:00:00')"
    )
    date_cond = "AND DATE(isl.logged_time) = %(date)s" if date else ""
    p         = {"date": date} if date else {}

    rows = frappe.db.sql(f"""
        SELECT COALESCE(SUM(pi.quantity), 0) AS qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi      ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor      ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc ON tbc.parent = tor.name AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc        ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc   ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
            ON pcflo.parent = tbc.work_order AND pcflo.physical_cell = pc.name
        WHERE pc.cell_name = 'KNITTING'
          AND isl.log_status = 'Completed'
          AND isl.operation = pcflo.last_operation
          AND {time_cond}
          {date_cond}
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
    """, p, as_dict=True)

    return int(rows[0].qty) if rows else 0


def _knitting_shift_sku_map(date):
    """
    Returns {(style, colour, size): total_knitting_cum_out} across both shifts.
    Used to correctly set KNITTING cum_out per SKU when walking the WIP chain.
    """
    date_cond = "AND DATE(isl.logged_time) = %(date)s" if date else ""
    p         = {"date": date} if date else {}

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            COALESCE(SUM(pi.quantity), 0) AS qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi      ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor      ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc ON tbc.parent = tor.name AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc        ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc   ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
            ON pcflo.parent = tbc.work_order AND pcflo.physical_cell = pc.name
        WHERE pc.cell_name = 'KNITTING'
          AND isl.log_status = 'Completed'
          AND isl.operation = pcflo.last_operation
          {date_cond}
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """, p, as_dict=True)

    return {(r.style, r.colour, r.size): int(r.qty) for r in rows}


def _get_applicable_cells_map():
    """
    Returns {(style, colour, size): set of cell_names} from pcflo.
    Mirrors shopfloor_performance._get_applicable_cells_map() exactly.
    KNITTING is excluded here (caller always adds it).
    """
    rows = frappe.db.sql(f"""
        SELECT DISTINCT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            pc.cell_name             AS cell_name
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor       ON tor.name = tbc.parent
        INNER JOIN `tabItem` itm                 ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                 ON pcflo.parent = tbc.work_order
        INNER JOIN `tabPhysical Cell` pc         ON pc.name = pcflo.physical_cell
        WHERE tbc.parentfield = 'bundle_configurations'
          AND pc.cell_name IN ({CELL_LIST_SQL})
    """, as_dict=True)

    result = defaultdict(set)
    for r in rows:
        result[(r.style, r.colour, r.size)].add(r.cell_name)
    return result