# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import re
import frappe
from collections import defaultdict
from datetime import date as _date
from frappe.utils import formatdate

_SIZE_ORDER = ["2XS", "XS", "S", "M", "L", "XL", "2XL", "XXL", "3XL", "XXXL", "4XL", "XXXXL"]

def _size_sort_key(size):
    upper = (size or "").upper().strip()
    if upper in _SIZE_ORDER:
        return (0, _SIZE_ORDER.index(upper), "")
    m = re.match(r"^(\d+)", upper)
    if m:
        return (1, int(m.group(1)), upper)
    return (2, 0, upper)

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

    # First logged date maps — earliest logged_time per (style, colour, size, cell)
    # for the first operation (IN) and last operation (OUT) respectively.
    # Used to compute per-cell "Days" label on the dashboard.
    cell_in_logged_date_map       = _get_cell_first_logged_date_map(op_type="first")
    cell_out_logged_date_map      = _get_cell_first_logged_date_map(op_type="last")

    # Last logged date maps — latest logged_time per (style, colour, size, cell)
    # for the last operation (OUT).  Used when cell is complete (out >= planned).
    cell_out_last_logged_date_map = _get_cell_last_logged_date_map()

    # Knitting first logged_time per (style, colour, size)
    # Used exclusively for the Lead Days calculation.
    knitting_logged_time_map = _get_knitting_first_logged_time_map()

    # Earliest logged_time per (style, colour, size) — used for sorting
    logged_time_map = _get_min_logged_time_map()

    # ── Aggregate at (buyer, season, style, colour) across all sizes ──────
    agg = defaultdict(lambda: {
        "order_qty":                   0,
        "planned_qty":                 0,
        "delivery_date":               None,
        "min_logged_time":             None,   # earliest isl.logged_time across sizes
        "cell_in":                     defaultdict(int),
        "cell_out":                    defaultdict(int),
        "cell_in_logged_date":         {},     # earliest IN logged date per cell
        "cell_out_logged_date":        {},     # earliest OUT logged date per cell
        "cell_out_last_logged_date":   {},     # latest OUT logged date per cell
        "knitting_first_logged":       None,   # earliest KNITTING logged_time
    })

    for (style, colour, size), info in order_map.items():
        key = (info.buyer or "", info.season or "", style, colour)
        agg[key]["order_qty"]   += int(info.order_qty or 0)
        agg[key]["planned_qty"] += int(info.planned_qty or 0)

        d = info.delivery_date
        if d and (agg[key]["delivery_date"] is None or d > agg[key]["delivery_date"]):
            agg[key]["delivery_date"] = d

        # Track the earliest logged_time seen for this (style, colour) group
        lt = logged_time_map.get((style, colour, size))
        if lt and (agg[key]["min_logged_time"] is None or lt < agg[key]["min_logged_time"]):
            agg[key]["min_logged_time"] = lt

        # Track the earliest KNITTING logged_time for Lead Days
        klt = knitting_logged_time_map.get((style, colour, size))
        if klt and (agg[key]["knitting_first_logged"] is None or klt < agg[key]["knitting_first_logged"]):
            agg[key]["knitting_first_logged"] = klt

        for cell in CELL_ORDER:
            agg[key]["cell_in"][cell]  += cell_in_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out"][cell] += cell_out_map.get((style, colour, size, cell), 0)

            # Track earliest IN logged date across sizes for this cell
            in_d = cell_in_logged_date_map.get((style, colour, size, cell))
            if in_d:
                ex = agg[key]["cell_in_logged_date"].get(cell)
                if ex is None or in_d < ex:
                    agg[key]["cell_in_logged_date"][cell] = in_d

            # Track earliest OUT logged date across sizes for this cell
            out_d = cell_out_logged_date_map.get((style, colour, size, cell))
            if out_d:
                ex = agg[key]["cell_out_logged_date"].get(cell)
                if ex is None or out_d < ex:
                    agg[key]["cell_out_logged_date"][cell] = out_d

            # Track latest OUT logged date across sizes for this cell
            last_out_d = cell_out_last_logged_date_map.get((style, colour, size, cell))
            if last_out_d:
                ex = agg[key]["cell_out_last_logged_date"].get(cell)
                if ex is None or last_out_d > ex:
                    agg[key]["cell_out_last_logged_date"][cell] = last_out_d

    # ── Build result rows ─────────────────────────────────────────────────
    result = []

    # Sort by earliest logged_time ascending (styles with the least/oldest logged
    # time appear first).  Styles that have no logs at all fall to the end.
    sorted_keys = sorted(
        agg.keys(),
        key=lambda k: (
            agg[k]["min_logged_time"] is None,          # None → pushed to end
            agg[k]["min_logged_time"] or "0000-00-00 00:00:00",
        )
    )

    today = _date.today()

    def _to_date(dt):
        """Convert datetime / date / str to date, or return None."""
        if dt is None:
            return None
        if hasattr(dt, "date"):      # datetime object
            return dt.date()
        if isinstance(dt, _date):    # already a date
            return dt
        try:                         # string "YYYY-MM-DD ..." or "YYYY-MM-DD"
            return _date.fromisoformat(str(dt)[:10])
        except Exception:
            return None

    # Cells that have no IN operation — use OUT logged date as the "first" reference
    NO_IN_CELLS = {"KNITTING", "FINAL CHECK"}

    for buyer, season, style, colour in sorted_keys:
        b = agg[(buyer, season, style, colour)]

        order_qty   = b["order_qty"]
        planned_qty = b["planned_qty"]

        # Build per-cell data:
        #   IN   = qty that completed the first operation of the cell
        #   OUT  = qty that completed the last operation of the cell
        #   %    = OUT / ORDER QTY × 100  (not OUT/IN)
        #
        #   days logic:
        #     • If cell_out >= planned_qty  → last OUT logged date − first IN logged date
        #     • Otherwise                   → today − first IN logged date
        #
        #   For NO_IN_CELLS (KNITTING, FINAL CHECK) the "first IN" reference is
        #   substituted with the first OUT logged date (these cells have no IN op).
        cells = {}
        for cell in CELL_ORDER:
            cell_in  = b["cell_in"].get(cell, 0)
            cell_out = b["cell_out"].get(cell, 0)
            pct      = round((cell_out / order_qty) * 100) if order_qty else 0

            # Determine the "start" reference date for this cell
            if cell in NO_IN_CELLS:
                first_ref = _to_date(b["cell_out_logged_date"].get(cell))
            else:
                first_ref = _to_date(b["cell_in_logged_date"].get(cell))

            # Days calculation
            if cell_out >= planned_qty:
                # Cell is complete: elapsed = last OUT − first IN (or first OUT for NO_IN cells)
                last_out_ref = _to_date(b["cell_out_last_logged_date"].get(cell))
                days = (last_out_ref - first_ref).days if (first_ref and last_out_ref) else None
            else:
                # Cell still in progress: elapsed = today − first IN (or first OUT for NO_IN cells)
                days = (today - first_ref).days if first_ref else None

            cells[cell] = {
                "in":   cell_in,
                "out":  cell_out,
                "pct":  pct,
                "days": days,
            }

        # ── Lead Days ──────────────────────────────────────────────────────
        # Start reference: first KNITTING IN (first logged_time in KNITTING)
        # • If PACKING OUT >= planned_qty → last PACKING OUT − first KNITTING IN
        # • Otherwise                     → today − first KNITTING IN
        knitting_first_ref = _to_date(b["knitting_first_logged"])
        packing_out        = cells["PACKING"]["out"]

        if packing_out >= planned_qty:
            packing_last_out_ref = _to_date(b["cell_out_last_logged_date"].get("PACKING"))
            lead_days = (
                (packing_last_out_ref - knitting_first_ref).days
                if (knitting_first_ref and packing_last_out_ref)
                else None
            )
        else:
            lead_days = (today - knitting_first_ref).days if knitting_first_ref else None

        # OVERALL COMPLETION = PACKING OUT / ORDER QTY × 100
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
            "lead_days":      lead_days,
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


def _get_min_logged_time_map():
    """
    Returns the earliest isl.logged_time per (style, colour, size).
    Used to sort styles so the one with the least (oldest) logged_time
    appears at the top of the dashboard.
    """
    rows = frappe.db.sql("""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            MIN(isl.logged_time)     AS min_logged_time
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
    return {(r.style, r.colour, r.size): r.min_logged_time for r in rows}


def _get_knitting_first_logged_time_map():
    """
    Returns the earliest isl.logged_time per (style, colour, size)
    for the KNITTING cell — used exclusively for Lead Days calculation.

    Lead Days = Current date − MIN(isl.logged_time) for KNITTING.
    """
    rows = frappe.db.sql("""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            MIN(isl.logged_time)     AS first_logged_time
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
        INNER JOIN `tabPhysical Cell` pc        ON pc.name = isl.physical_cell
        WHERE pc.cell_name = 'KNITTING'
          AND isl.log_status = 'Completed'
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """, as_dict=True)
    return {(r.style, r.colour, r.size): r.first_logged_time for r in rows}


def _get_cell_op_map(op_type="last"):
    """
    Returns qty per (style, colour, size, cell_name) for either
    the first or last operation of each physical cell.

    op_type = "first"  →  cell IN
    op_type = "last"   →  cell OUT

    For most cells, the operation name is read dynamically from
    pcflo.first_operation / pcflo.last_operation.

    Exception — MENDING uses hardcoded operation names:
        first  →  'MENDING IN'
        last   →  'MENDING OUT'
    """
    op_field         = "first_operation" if op_type == "first" else "last_operation"
    mending_op       = "MENDING IN"      if op_type == "first" else "MENDING OUT"
    cell_list        = ", ".join([f"'{c}'" for c in CELL_ORDER])

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
        WHERE isl.operation = CASE
                WHEN pc.cell_name = 'MENDING' THEN '{mending_op}'
                ELSE pcflo.{op_field}
              END
          AND isl.log_status = 'Completed'
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): int(r.qty) for r in rows}


def _get_cell_first_logged_date_map(op_type="first"):
    """
    Returns the earliest (MIN) logged_time per (style, colour, size, cell_name)
    for either the first (IN) or last (OUT) operation of each cell.

    op_type = "first"  →  cell IN first logged date
    op_type = "last"   →  cell OUT first logged date

    Used to determine when a cell started for a given style.
    Uses the same operation-matching logic as _get_cell_op_map.
    """
    op_field   = "first_operation" if op_type == "first" else "last_operation"
    mending_op = "MENDING IN"      if op_type == "first" else "MENDING OUT"
    cell_list  = ", ".join([f"'{c}'" for c in CELL_ORDER])

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            pc.cell_name                                AS cell_name,
            MIN(isl.logged_time)                        AS first_logged_date
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
        WHERE isl.operation = CASE
                WHEN pc.cell_name = 'MENDING' THEN '{mending_op}'
                ELSE pcflo.{op_field}
              END
          AND isl.log_status = 'Completed'
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): r.first_logged_date for r in rows}


def _get_cell_last_logged_date_map():
    """
    Returns the latest (MAX) logged_time per (style, colour, size, cell_name)
    for the last operation (OUT) of each cell.

    Used when a cell is complete (cell_out >= planned_qty) to compute:
        days = last OUT logged date − first IN logged date

    Also used for Lead Days when PACKING is complete:
        lead_days = last PACKING OUT logged date − first KNITTING IN logged date

    Uses the same operation-matching logic as _get_cell_op_map(op_type="last").
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            pc.cell_name                                AS cell_name,
            MAX(isl.logged_time)                        AS last_logged_date
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
        WHERE isl.operation = CASE
                WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT'
                ELSE pcflo.last_operation
              END
          AND isl.log_status = 'Completed'
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): r.last_logged_date for r in rows}


def _get_applicable_cells_map():
    """
    Returns {(style, colour, size) → set(cell_names)} from the Cut Kit
    operation map (tabPhysical Cell First and Last Operation).
    KNITTING is excluded here — callers add it explicitly.
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])
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
          AND pc.cell_name IN ({cell_list})
    """, as_dict=True)
    result = defaultdict(set)
    for r in rows:
        result[(r.style, r.colour, r.size)].add(r.cell_name)
    return result


def _get_outsourced_cells_map():
    """
    Returns {(style, colour, size) → set(cell_names)} for cells where
    production_type = 'Outsourced' in the Cut Kit Operations child table.

    The Cut Kit Operations child table lives under the Work Order doctype
    (tbc.work_order = Work Order name).  Each row has:
        physical_cell   — links to tabPhysical Cell
        production_type — 'Outsourced' or 'In-House'

    Since the operation sequence (and therefore production_type per cell)
    is mapped at the style level, all work orders for the same style will
    share the same outsourced/in-house designation per cell.  A DISTINCT
    query is therefore sufficient — no aggregation needed.
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])
    rows = frappe.db.sql(f"""
        SELECT DISTINCT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            pc.cell_name             AS cell_name
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor       ON tor.name = tbc.parent
        INNER JOIN `tabItem` itm                 ON itm.name = tor.item
        INNER JOIN `tabCut Kit Operations` cko   ON cko.parent = tbc.work_order
        INNER JOIN `tabPhysical Cell` pc         ON pc.name = cko.physical_cell
        WHERE tbc.parentfield = 'bundle_configurations'
          AND cko.production_type  = 'Outsourced'
          AND pc.cell_name IN ({cell_list})
    """, as_dict=True)

    result = defaultdict(set)
    for r in rows:
        result[(r.style, r.colour, r.size)].add(r.cell_name)
    return result


@frappe.whitelist()
def get_style_sizewise_data(style, colour):
    """
    Returns cumulative size-wise IN / OUT data for every applicable cell
    of the given (style, colour).  Drives the size-wise popup.

    WIP rules:
      - Outsourced cells: wip_pending = 0, wip_actual = 0
      - The prev_total_out chain reference is only advanced by in-house cells,
        so that the next in-house cell's wip_pending correctly skips over any
        outsourced cells in between.
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])

    # ── Order info per size ───────────────────────────────────────────────
    order_rows = frappe.db.sql("""
        SELECT
            so.custom_brand                             AS buyer,
            stm.custom_season                           AS season,
            MAX(so.delivery_date)                       AS delivery_date,
            tbc.size                                    AS size,
            COALESCE(SUM(soi.custom_order_qty), 0)      AS order_qty,
            COALESCE(SUM(soi.qty), 0)                   AS planned_qty
        FROM (
            SELECT DISTINCT sales_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
        INNER JOIN `tabSales Order` so       ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
                                            AND soi.custom_size = tbc.size
        INNER JOIN `tabItem` itm             ON itm.name = soi.item_code
        INNER JOIN `tabStyle Master` stm     ON stm.name = itm.custom_style_master
        WHERE itm.custom_style_master = %(style)s
          AND itm.custom_colour_name  = %(colour)s
        GROUP BY so.custom_brand, stm.custom_season, tbc.size
    """, {"style": style, "colour": colour}, as_dict=True)

    if not order_rows:
        return None

    buyer = order_rows[0].buyer or ""
    season = order_rows[0].season or ""
    delivery_date = None
    sizes_info = {}
    total_order_qty = total_planned_qty = 0

    for r in order_rows:
        sizes_info[r.size] = {
            "order_qty":   int(r.order_qty   or 0),
            "planned_qty": int(r.planned_qty or 0),
        }
        total_order_qty   += int(r.order_qty   or 0)
        total_planned_qty += int(r.planned_qty or 0)
        d = r.delivery_date
        if d and (delivery_date is None or d > delivery_date):
            delivery_date = d

    sorted_sizes = sorted(sizes_info.keys(), key=_size_sort_key)

    # ── Applicable cells from operation map ───────────────────────────────
    applicable_cells_map = _get_applicable_cells_map()
    applicable_cells = set()
    for size in sizes_info:
        applicable_cells |= applicable_cells_map.get((style, colour, size), set())

    # ── Outsourced cells for this style/colour ────────────────────────────
    # Union across all sizes (outsourced = style-level per cell, so the
    # result is the same for every size — the union is a safety net).
    outsourced_cells_map = _get_outsourced_cells_map()
    outsourced_cells = set()
    for size in sizes_info:
        outsourced_cells |= outsourced_cells_map.get((style, colour, size), set())

    # ── Cumulative IN / OUT per (style, colour, size, cell) ───────────────
    scan_rows = frappe.db.sql(f"""
        SELECT
            tbc.size                                    AS size,
            pc.cell_name                                AS cell_name,
            pcflo.first_operation                       AS first_op,
            pcflo.last_operation                        AS last_op,
            isl.operation                               AS operation,
            COALESCE(SUM(pi.quantity), 0)               AS qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc                                       ON tbc.parent = tor.name
                                                   AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component
                                                   AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                   ON pcflo.parent = tbc.work_order
                                                   AND pcflo.physical_cell = pc.name
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE itm.custom_style_master = %(style)s
          AND itm.custom_colour_name  = %(colour)s
          AND isl.log_status = 'Completed'
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
          AND isl.operation IN (
              CASE WHEN pc.cell_name = 'MENDING' THEN 'MENDING IN'  ELSE pcflo.first_operation END,
              CASE WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT' ELSE pcflo.last_operation  END
          )
        GROUP BY tbc.size, pc.cell_name, pcflo.first_operation, pcflo.last_operation, isl.operation
    """, {"style": style, "colour": colour}, as_dict=True)

    # Organise into {(size, cell): {first_op: qty, last_op: qty}}
    scan_map = defaultdict(lambda: {"in": 0, "out": 0})
    for r in scan_rows:
        key = (r.size, r.cell_name)
        mending_first = "MENDING IN"
        mending_last  = "MENDING OUT"
        if r.cell_name == "MENDING":
            if r.operation == mending_first:
                scan_map[key]["in"]  += int(r.qty)
            if r.operation == mending_last:
                scan_map[key]["out"] += int(r.qty)
        else:
            if r.operation == r.first_op:
                scan_map[key]["in"]  += int(r.qty)
            if r.operation == r.last_op:
                scan_map[key]["out"] += int(r.qty)

    # ── Build per-cell rows ───────────────────────────────────────────────
    #
    # prev_total_out tracks the OUT qty of the last IN-HOUSE cell only.
    # It is NOT updated when an outsourced cell is processed, so that the
    # next in-house cell's wip_pending correctly skips over outsourced cells.
    #
    # Example — CUTTING(IH) → LINKING(OS) → SEWING(IH):
    #   After CUTTING  : prev_total_out = CUTTING_OUT
    #   LINKING (OS)   : wip_pending=0, wip_actual=0; prev_total_out unchanged
    #   SEWING  (IH)   : wip_pending = CUTTING_OUT − SEWING_IN  ✓
    #
    prev_total_out = 0
    cell_rows = []

    for cell in CELL_ORDER:
        if cell not in applicable_cells:
            continue

        is_outsourced = cell in outsourced_cells

        in_by_size = {}
        out_by_size = {}
        total_in = total_out = 0

        for size in sorted_sizes:
            sz_order_qty = sizes_info[size]["order_qty"]
            qty_in  = scan_map[(size, cell)]["in"]
            qty_out = scan_map[(size, cell)]["out"]
            in_by_size[size] = {
                "qty": qty_in,
                "pct": round(qty_in  / sz_order_qty * 100) if sz_order_qty else 0,
            }
            out_by_size[size] = {
                "qty": qty_out,
                "pct": round(qty_out / sz_order_qty * 100) if sz_order_qty else 0,
            }
            total_in  += qty_in
            total_out += qty_out

        if is_outsourced:
            # Outsourced cell: suppress WIP entirely.
            # Do NOT advance prev_total_out so the next in-house cell's
            # wip_pending still references the last in-house cell's OUT.
            wip_pending = 0
            wip_actual  = 0
        else:
            # In-house cell: normal WIP chain calculation.
            wip_pending    = max(0, prev_total_out - total_in)
            wip_actual     = max(0, total_in - total_out)
            prev_total_out = total_out   # advance the chain reference

        in_balance_pct  = round(total_in  / total_order_qty * 100) if total_order_qty else 0
        out_balance_pct = round(total_out / total_order_qty * 100) if total_order_qty else 0

        cell_rows.append({
            "cell":            cell,
            "is_outsourced":   is_outsourced,
            "in_by_size":      in_by_size,
            "out_by_size":     out_by_size,
            "total_in":        total_in,
            "total_out":       total_out,
            "wip_pending":     wip_pending,
            "wip_actual":      wip_actual,
            "in_balance_pct":  in_balance_pct,
            "out_balance_pct": out_balance_pct,
        })

    return {
        "style":         style,
        "colour":        colour,
        "buyer":         buyer,
        "season":        season,
        "delivery_date": formatdate(delivery_date, "dd-mm-yyyy") if delivery_date else "",
        "order_qty":     total_order_qty,
        "planned_qty":   total_planned_qty,
        "sizes":         sorted_sizes,
        "cells":         cell_rows,
    }