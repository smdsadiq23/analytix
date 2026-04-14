# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt
#
# Owner Dashboard — optimised backend
#
# The WIP / Pending In values must exactly match the shopfloor_performance
# dashboard. The shopfloor computes these per (style, colour, size) using
# per-style applicable_cells from the Cut Kit operation map (pcflo), then
# sums across styles. The global aggregation done here must produce the same
# result, which requires:
#
#   1. applicable_set  — from pcflo (cells that have at least one configured
#                         operation), NOT from scan data.  Scan-data detection
#                         fails for cells like PRODUCTION where items skip the
#                         first_operation scan entirely.
#
#   2. cum_in / cum_out — use EXACT same first_operation / last_operation
#                         scan query as shopfloor (with MENDING IN/OUT special
#                         case, tabItem + tabSales Order joins included),
#                         aggregated globally across all styles/sizes.
#
#   3. cum_out patching — non-applicable cells must have their cum_out set to
#                         their nearest applicable predecessor's cum_out, so
#                         the next applicable cell computes the correct
#                         pending_in.  Without this, a non-applicable cell
#                         with 0 cum_in leaks the predecessor's cum_out as a
#                         huge pending_in for the following cell.
#
#   4. predecessor walk — when computing pending_in, walk back to the nearest
#                         cell that is IN applicable_set (including KNITTING),
#                         not just the nearest with scan data.

import frappe
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

# ── Shared JOIN block ─────────────────────────────────────────────────────────
# Identical to shopfloor_performance._get_cell_op_map_for_period, including
# the tabItem and tabSales Order joins that were missing from the original
# owner dashboard (their absence could skew counts).
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
    """MENDING uses named operations; all other cells use pcflo first/last."""
    return f"CASE WHEN pc.cell_name = 'MENDING' THEN '{op_label}' ELSE pcflo.{field} END"


@frappe.whitelist()
def get_owner_dashboard_data(date=None):
    """
    Returns a dict keyed by cell_name:
        { cell_name: { input, output, pending_in, wip, applicable } }
    KNITTING also carries: { shift1, shift2 }
    """
    if not date:
        date = _date.today().isoformat()

    params = {"date": date}

    # ── Daily IN / OUT (selected date) ───────────────────────────────────
    daily_in_rows = _run(f"""
        SELECT pc.cell_name, COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case('MENDING IN', 'first_operation')}
          AND DATE(isl.logged_time) = %(date)s
        GROUP BY pc.cell_name
    """, params)

    daily_out_rows = _run(f"""
        SELECT pc.cell_name, COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case('MENDING OUT', 'last_operation')}
          AND DATE(isl.logged_time) = %(date)s
        GROUP BY pc.cell_name
    """, params)

    # ── Cumulative IN / OUT (all time) ───────────────────────────────────
    cum_in_rows = _run(f"""
        SELECT pc.cell_name, COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case('MENDING IN', 'first_operation')}
        GROUP BY pc.cell_name
    """, {})

    cum_out_rows = _run(f"""
        SELECT pc.cell_name, COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case('MENDING OUT', 'last_operation')}
        GROUP BY pc.cell_name
    """, {})

    # ── KNITTING shifts ───────────────────────────────────────────────────
    knitting_shift1     = _knitting_shift(date, shift=1)
    knitting_shift2     = _knitting_shift(date, shift=2)
    knitting_shift1_cum = _knitting_shift(None, shift=1)
    knitting_shift2_cum = _knitting_shift(None, shift=2)

    # ── Applicable cells from pcflo ───────────────────────────────────────
    applicable_set = _get_applicable_cells_global()
    applicable_set.add("KNITTING")  # always applicable (shift-map driven)

    # ── Mutable lookup dicts ──────────────────────────────────────────────
    d_in  = {r["cell_name"]: int(r["qty"]) for r in daily_in_rows}
    d_out = {r["cell_name"]: int(r["qty"]) for r in daily_out_rows}
    c_in  = {r["cell_name"]: int(r["qty"]) for r in cum_in_rows}
    c_out = {r["cell_name"]: int(r["qty"]) for r in cum_out_rows}

    # KNITTING cumulative output = shift totals (not pcflo last_operation scans)
    knitting_cum = knitting_shift1_cum + knitting_shift2_cum
    c_out["KNITTING"] = knitting_cum

    # ── Patch non-applicable cells' cum_out ──────────────────────────────
    # Mirrors shopfloor_performance.py "Patch cum_out for non-applicable cells".
    # Sets each non-applicable cell's cum_out to its nearest applicable
    # predecessor's cum_out so that the following applicable cell sees the
    # correct predecessor value when computing pending_in.
    for i, cell in enumerate(CELL_ORDER):
        if i == 0 or cell in applicable_set:
            continue
        for j in range(i - 1, -1, -1):
            pred = CELL_ORDER[j]
            if pred in applicable_set or j == 0:
                c_out[cell] = c_out.get(pred, 0)
                break

    # ── Build result ──────────────────────────────────────────────────────
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

        inp = d_in.get(cell, 0)
        out = d_out.get(cell, 0)

        if cell not in applicable_set:
            result[cell] = {
                "input":      inp,
                "output":     out,
                "pending_in": 0,
                "wip":        0,
                "applicable": False,
            }
            continue

        # Nearest applicable predecessor (including KNITTING)
        prev_cum_out = 0
        for j in range(i - 1, -1, -1):
            pred = CELL_ORDER[j]
            if pred in applicable_set:
                prev_cum_out = c_out.get(pred, 0)
                break

        cur_cum_in  = c_in.get(cell, 0)
        cur_cum_out = c_out.get(cell, 0)

        result[cell] = {
            "input":      inp,
            "output":     out,
            "pending_in": max(0, prev_cum_out - cur_cum_in),
            "wip":        max(0, cur_cum_in  - cur_cum_out),
            "applicable": True,
        }

    return result


# ── Private helpers ───────────────────────────────────────────────────────────

def _run(sql, params):
    return frappe.db.sql(sql, params, as_dict=True)


def _knitting_shift(date, shift):
    """
    Total KNITTING output for shift 1 (10:00–20:00) or shift 2 (20:00–10:00).
    date=None returns all-time cumulative.
    Query is identical to shopfloor_performance._get_knitting_shift_map_for_period.
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


def _get_applicable_cells_global():
    """
    Returns the set of cell_names that have at least one pcflo row across ALL
    work orders — the union of all per-style applicable_cells sets used by
    shopfloor_performance._get_applicable_cells_map().

    Uses pcflo (Cut Kit operation map) as the source of truth, not scan data,
    because some cells (e.g. PRODUCTION) may have 0 first_operation scans yet
    still be applicable.
    """
    rows = frappe.db.sql(f"""
        SELECT DISTINCT pc.cell_name
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor       ON tor.name = tbc.parent
        INNER JOIN `tabItem` itm                 ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                 ON pcflo.parent = tbc.work_order
        INNER JOIN `tabPhysical Cell` pc         ON pc.name = pcflo.physical_cell
        WHERE tbc.parentfield = 'bundle_configurations'
          AND pc.cell_name IN ({CELL_LIST_SQL})
    """, as_dict=True)
    return {r["cell_name"] for r in rows}