# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt
#
# Owner Dashboard — optimised backend
#
# Original shopfloor_performance.get_dashboard_data fires 21 SQL queries
# (MTD, YTD, date-log maps, lead-days, per-style rows …) and returns
# thousands of per-style rows that the JS then re-aggregates.
#
# The owner dashboard only needs four numbers per section:
#   Input, Output, Pending In (Ready for Input), WIP
# This module fetches exactly that with 8 targeted queries that aggregate
# directly in SQL, cutting load time from ~30s to 2-3s.

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

# Shared JOIN block reused across cell queries
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
    INNER JOIN `tabPhysical Cell` pc
        ON pc.name = isl.physical_cell
    INNER JOIN `tabTracking Component` tc
        ON tc.name = pi.component AND tc.is_main = 1
    INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
        ON pcflo.parent = tbc.work_order
        AND pcflo.physical_cell = pc.name
    WHERE isl.log_status = 'Completed'
      AND pc.cell_name IN ({CELL_LIST_SQL})
      AND (
          isl.status IN ('Counted', 'Activated', 'Pass')
          OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
      )
"""


def _op_case(op_label, field):
    return f"CASE WHEN pc.cell_name = 'MENDING' THEN '{op_label}' ELSE pcflo.{field} END"


@frappe.whitelist()
def get_owner_dashboard_data(date=None):
    """
    Returns a dict keyed by cell_name with four values needed by the chart:
        { cell_name: { input, output, pending_in, wip } }
    Plus KNITTING breakdown:
        { "KNITTING": { shift1, shift2, output, input: None, ... } }
    """
    if not date:
        date = _date.today().isoformat()

    params = {"date": date}

    # ── 1. Daily INPUT per section (first_operation scans, selected date) ─
    daily_in = _run(f"""
        SELECT pc.cell_name, COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case('MENDING IN', 'first_operation')}
          AND DATE(isl.logged_time) = %(date)s
        GROUP BY pc.cell_name
    """, params)

    # ── 2. Daily OUTPUT per section (last_operation scans, selected date) ─
    daily_out = _run(f"""
        SELECT pc.cell_name, COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case('MENDING OUT', 'last_operation')}
          AND DATE(isl.logged_time) = %(date)s
        GROUP BY pc.cell_name
    """, params)

    # ── 3. Cumulative INPUT per section (all time, for pending_in) ────────
    cum_in = _run(f"""
        SELECT pc.cell_name, COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case('MENDING IN', 'first_operation')}
        GROUP BY pc.cell_name
    """, {})

    # ── 4. Cumulative OUTPUT per section (all time, for wip) ─────────────
    cum_out = _run(f"""
        SELECT pc.cell_name, COALESCE(SUM(pi.quantity), 0) AS qty
        {_SCAN_JOINS}
          AND isl.operation = {_op_case('MENDING OUT', 'last_operation')}
        GROUP BY pc.cell_name
    """, {})

    # ── 5-6. KNITTING daily shifts ────────────────────────────────────────
    knitting_shift1     = _knitting_shift(date, shift=1)
    knitting_shift2     = _knitting_shift(date, shift=2)

    # ── 7-8. KNITTING cumulative shifts (for WIP chain) ───────────────────
    knitting_shift1_cum = _knitting_shift(None, shift=1)
    knitting_shift2_cum = _knitting_shift(None, shift=2)

    # ── 9. Applicable cells (determines which cells have WIP) ─────────────
    applicable_set = _get_applicable_cells()

    # ── Build lookup dicts ────────────────────────────────────────────────
    d_in  = {r["cell_name"]: int(r["qty"]) for r in daily_in}
    d_out = {r["cell_name"]: int(r["qty"]) for r in daily_out}
    c_in  = {r["cell_name"]: int(r["qty"]) for r in cum_in}
    c_out = {r["cell_name"]: int(r["qty"]) for r in cum_out}

    # KNITTING cumulative output comes from shift totals, not last_operation scans
    knitting_cum = knitting_shift1_cum + knitting_shift2_cum
    c_out["KNITTING"] = knitting_cum

    # ── Compute section results ───────────────────────────────────────────
    result = {}

    for i, cell in enumerate(CELL_ORDER):
        if i == 0:
            # KNITTING — output = daily shifts; no input/pending/wip concept
            result[cell] = {
                "input":      None,
                "output":     knitting_shift1 + knitting_shift2,
                "shift1":     knitting_shift1,
                "shift2":     knitting_shift2,
                "pending_in": None,
                "wip":        None,
            }
            continue

        inp = d_in.get(cell, 0)
        out = d_out.get(cell, 0)

        if cell not in applicable_set:
            result[cell] = {
                "input": inp, "output": out,
                "pending_in": 0, "wip": 0, "applicable": False,
            }
            continue

        # Nearest applicable predecessor's cumulative output
        prev_cum_out = 0
        for j in range(i - 1, -1, -1):
            pred = CELL_ORDER[j]
            if pred == "KNITTING" or pred in applicable_set:
                prev_cum_out = c_out.get(pred, 0)
                break

        cur_cum_out = c_out.get(cell, 0)
        cur_cum_in  = c_in.get(cell, 0)

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
    """Total KNITTING output for shift 1 (10:00-20:00) or shift 2 (20:00-10:00).
    If date is None, returns the all-time cumulative total."""
    time_cond = (
        "TIME(isl.logged_time) >= '10:00:00' AND TIME(isl.logged_time) < '20:00:00'"
        if shift == 1
        else "(TIME(isl.logged_time) >= '20:00:00' OR TIME(isl.logged_time) < '10:00:00')"
    )
    date_cond = "AND DATE(isl.logged_time) = %(date)s" if date else ""
    params    = {"date": date} if date else {}

    rows = frappe.db.sql(f"""
        SELECT COALESCE(SUM(pi.quantity), 0) AS qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi      ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor      ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc ON tbc.parent = tor.name AND tbc.size = pi.size
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
    """, params, as_dict=True)

    return int(rows[0].qty) if rows else 0


def _get_applicable_cells():
    """Set of cell_names that have at least one pcflo row across all work orders."""
    rows = frappe.db.sql(f"""
        SELECT DISTINCT pc.cell_name
        FROM `tabPhysical Cell First and Last Operation` pcflo
        INNER JOIN `tabPhysical Cell` pc ON pc.name = pcflo.physical_cell
        WHERE pc.cell_name IN ({CELL_LIST_SQL})
    """, as_dict=True)
    return {r["cell_name"] for r in rows}
