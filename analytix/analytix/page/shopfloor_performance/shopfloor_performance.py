# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict
from datetime import date as _date
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
def get_dashboard_data(date=None):
    # Default to today if no date provided
    if not date:
        date = _date.today().isoformat()

    order_map = _get_order_map()
    if not order_map:
        return []

    # Which physical cells are actually in the operation map for each (style, colour, size)?
    # Used to skip non-applicable cells in WIP and pending_in calculations.
    applicable_cells_map = _get_applicable_cells_map()

    # ── Daily maps (scans on the selected date only) ──────────────────────
    daily_condition = "DATE(isl.logged_time) = %(filter_date)s"
    daily_params    = {"filter_date": date}

    cell_in_map  = _get_cell_op_map_for_period(op_type="first", date_condition=daily_condition, params=daily_params)
    cell_out_map = _get_cell_op_map_for_period(op_type="last",  date_condition=daily_condition, params=daily_params)

    # Knitting shift maps — shift 1: 10am–8pm, shift 2: 8pm–next day 10am (daily)
    knitting_shift1_map = _get_knitting_shift_map_for_period(shift=1, date_condition=daily_condition, params=daily_params)
    knitting_shift2_map = _get_knitting_shift_map_for_period(shift=2, date_condition=daily_condition, params=daily_params)

    # ── Cumulative maps (all-time, no date filter — used for WIP & popup) ─
    cum_condition = "1=1"
    cum_params    = {}

    cell_in_cum_map         = _get_cell_op_map_for_period(op_type="first", date_condition=cum_condition, params=cum_params)
    cell_out_cum_map        = _get_cell_op_map_for_period(op_type="last",  date_condition=cum_condition, params=cum_params)
    knitting_shift1_cum_map = _get_knitting_shift_map_for_period(shift=1, date_condition=cum_condition, params=cum_params)
    knitting_shift2_cum_map = _get_knitting_shift_map_for_period(shift=2, date_condition=cum_condition, params=cum_params)

    # ── MTD maps (scans from start of selected month up to and including selected date) ──
    mtd_condition = (
        "YEAR(isl.logged_time) = YEAR(%(filter_date)s) "
        "AND MONTH(isl.logged_time) = MONTH(%(filter_date)s) "
        "AND DATE(isl.logged_time) <= %(filter_date)s"
    )
    mtd_params = {"filter_date": date}

    cell_out_mtd_map = _get_cell_op_map_for_period(op_type="last", date_condition=mtd_condition, params=mtd_params)
    knitting_shift1_mtd = _get_knitting_shift_map_for_period(shift=1, date_condition=mtd_condition, params=mtd_params)
    knitting_shift2_mtd = _get_knitting_shift_map_for_period(shift=2, date_condition=mtd_condition, params=mtd_params)

    # ── YTD maps (scans from start of selected year up to and including selected date) ──
    ytd_condition = (
        "YEAR(isl.logged_time) = YEAR(%(filter_date)s) "
        "AND DATE(isl.logged_time) <= %(filter_date)s"
    )
    ytd_params = {"filter_date": date}

    cell_out_ytd_map = _get_cell_op_map_for_period(op_type="last", date_condition=ytd_condition, params=ytd_params)
    knitting_shift1_ytd = _get_knitting_shift_map_for_period(shift=1, date_condition=ytd_condition, params=ytd_params)
    knitting_shift2_ytd = _get_knitting_shift_map_for_period(shift=2, date_condition=ytd_condition, params=ytd_params)

    # ── Date reference maps (still cumulative — for lead days / completion tracking) ──
    cell_in_logged_date_map       = _get_cell_first_logged_date_map(op_type="first")
    cell_out_logged_date_map      = _get_cell_first_logged_date_map(op_type="last")
    cell_out_last_logged_date_map = _get_cell_last_logged_date_map()
    knitting_logged_time_map      = _get_knitting_first_logged_time_map()
    logged_time_map               = _get_min_logged_time_map()

    # ── Aggregate at (buyer, season, style, colour) across all sizes ──────
    agg = defaultdict(lambda: {
        "order_qty":                   0,
        "planned_qty":                 0,
        "delivery_date":               None,
        "min_logged_time":             None,
        "cell_in":                     defaultdict(int),
        "cell_out":                    defaultdict(int),
        "cell_out_mtd":                defaultdict(int),
        "cell_out_ytd":                defaultdict(int),
        "cell_out_cum":                defaultdict(int),
        "cell_in_cum":                 defaultdict(int),
        "cell_in_logged_date":         {},
        "cell_out_logged_date":        {},
        "cell_out_last_logged_date":   {},
        "knitting_first_logged":       None,
        "knitting_shift1":             0,
        "knitting_shift2":             0,
        "knitting_shift1_mtd":         0,
        "knitting_shift2_mtd":         0,
        "knitting_shift1_ytd":         0,
        "knitting_shift2_ytd":         0,
        "knitting_shift1_cum":         0,
        "knitting_shift2_cum":         0,
        # Cells actually present in the Cut Kit operation map for this group.
        # KNITTING is always included (output sourced from shift maps, not pcflo).
        "applicable_cells":            set(),
    })

    for (style, colour, size), info in order_map.items():
        key = (info.buyer or "", info.season or "", style, colour)
        agg[key]["order_qty"]   += int(info.order_qty or 0)
        agg[key]["planned_qty"] += int(info.planned_qty or 0)

        # Accumulate applicable cells from the Cut Kit operation map.
        # KNITTING is always included because its output is tracked via shift maps.
        sku_cells = applicable_cells_map.get((style, colour, size), set())
        agg[key]["applicable_cells"] |= sku_cells
        agg[key]["applicable_cells"].add("KNITTING")

        d = info.delivery_date
        if d and (agg[key]["delivery_date"] is None or d > agg[key]["delivery_date"]):
            agg[key]["delivery_date"] = d

        lt = logged_time_map.get((style, colour, size))
        if lt and (agg[key]["min_logged_time"] is None or lt < agg[key]["min_logged_time"]):
            agg[key]["min_logged_time"] = lt

        klt = knitting_logged_time_map.get((style, colour, size))
        if klt and (agg[key]["knitting_first_logged"] is None or klt < agg[key]["knitting_first_logged"]):
            agg[key]["knitting_first_logged"] = klt

        for cell in CELL_ORDER:
            agg[key]["cell_in"][cell]      += cell_in_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out"][cell]     += cell_out_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out_mtd"][cell] += cell_out_mtd_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out_ytd"][cell] += cell_out_ytd_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out_cum"][cell] += cell_out_cum_map.get((style, colour, size, cell), 0)
            agg[key]["cell_in_cum"][cell]  += cell_in_cum_map.get((style, colour, size, cell), 0)

            in_d = cell_in_logged_date_map.get((style, colour, size, cell))
            if in_d:
                ex = agg[key]["cell_in_logged_date"].get(cell)
                if ex is None or in_d < ex:
                    agg[key]["cell_in_logged_date"][cell] = in_d

            out_d = cell_out_logged_date_map.get((style, colour, size, cell))
            if out_d:
                ex = agg[key]["cell_out_logged_date"].get(cell)
                if ex is None or out_d < ex:
                    agg[key]["cell_out_logged_date"][cell] = out_d

            last_out_d = cell_out_last_logged_date_map.get((style, colour, size, cell))
            if last_out_d:
                ex = agg[key]["cell_out_last_logged_date"].get(cell)
                if ex is None or last_out_d > ex:
                    agg[key]["cell_out_last_logged_date"][cell] = last_out_d

        # Daily knitting shifts
        agg[key]["knitting_shift1"] += knitting_shift1_map.get((style, colour, size), 0)
        agg[key]["knitting_shift2"] += knitting_shift2_map.get((style, colour, size), 0)

        # MTD knitting shifts
        agg[key]["knitting_shift1_mtd"] += knitting_shift1_mtd.get((style, colour, size), 0)
        agg[key]["knitting_shift2_mtd"] += knitting_shift2_mtd.get((style, colour, size), 0)

        # YTD knitting shifts
        agg[key]["knitting_shift1_ytd"] += knitting_shift1_ytd.get((style, colour, size), 0)
        agg[key]["knitting_shift2_ytd"] += knitting_shift2_ytd.get((style, colour, size), 0)

        # Cumulative knitting shifts (for WIP)
        agg[key]["knitting_shift1_cum"] += knitting_shift1_cum_map.get((style, colour, size), 0)
        agg[key]["knitting_shift2_cum"] += knitting_shift2_cum_map.get((style, colour, size), 0)

    # ── Build result rows ─────────────────────────────────────────────────
    result = []

    sorted_keys = sorted(
        agg.keys(),
        key=lambda k: (
            agg[k]["min_logged_time"] is None,
            agg[k]["min_logged_time"] or "0000-00-00 00:00:00",
        )
    )

    today = _date.today()

    def _to_date(dt):
        if dt is None:
            return None
        if hasattr(dt, "date"):
            return dt.date()
        if isinstance(dt, _date):
            return dt
        try:
            return _date.fromisoformat(str(dt)[:10])
        except Exception:
            return None

    NO_IN_CELLS = {"KNITTING", "FINAL CHECK"}

    for buyer, season, style, colour in sorted_keys:
        b = agg[(buyer, season, style, colour)]

        order_qty   = b["order_qty"]
        planned_qty = b["planned_qty"]

        # Pre-compute KNITTING cum_out from shift maps (used throughout WIP logic below).
        knitting_cum = b["knitting_shift1_cum"] + b["knitting_shift2_cum"]

        # Cells that are actually part of this style's Cut Kit operation map.
        # Fall back to all cells if the map is empty (e.g. legacy data with no pcflo rows).
        applicable_cells = b["applicable_cells"] or set(CELL_ORDER)

        cells = {}
        for i, cell in enumerate(CELL_ORDER):
            cell_in      = b["cell_in"].get(cell, 0)
            cell_out     = b["cell_out"].get(cell, 0)
            cell_out_mtd = b["cell_out_mtd"].get(cell, 0)
            cell_out_ytd = b["cell_out_ytd"].get(cell, 0)
            # For KNITTING, override cum_out with the authoritative shift-map total.
            cell_out_cum = knitting_cum if cell == "KNITTING" else b["cell_out_cum"].get(cell, 0)
            cell_in_cum  = b["cell_in_cum"].get(cell, 0)
            pct          = round((cell_out / order_qty) * 100) if order_qty else 0

            # WIP uses cumulative figures:
            #   Actual WIP  = cum_in − cum_out  (material entered but not yet exited)
            #   Pending In  = prev_applicable_cum_out − cum_in
            #
            # Only compute WIP for cells that are in the Cut Kit operation map.
            # Non-applicable cells (e.g. CUTTING skipped for a plain knit style) get None
            # so the frontend can render them as N/A rather than showing misleading zeros.
            if i == 0:
                # KNITTING: wip not applicable; cum_out is set from shift maps above.
                actual_wip = None
                pending_in = None
            elif cell not in applicable_cells:
                # This physical cell is not part of the operation map for this style.
                actual_wip = None
                pending_in = None
            else:
                # Walk backwards to find the nearest applicable predecessor cell.
                prev_applicable = None
                for j in range(i - 1, -1, -1):
                    if CELL_ORDER[j] in applicable_cells:
                        prev_applicable = CELL_ORDER[j]
                        break

                if prev_applicable == "KNITTING":
                    prev_out_cum = knitting_cum
                elif prev_applicable:
                    prev_out_cum = b["cell_out_cum"].get(prev_applicable, 0)
                else:
                    prev_out_cum = 0

                actual_wip = max(0, cell_in_cum - cell_out_cum)
                pending_in = max(0, prev_out_cum - cell_in_cum)

            # Legacy wip field = actual_wip (keeps card display unchanged)
            wip = actual_wip

            # Days calculation (still cumulative — unchanged)
            if cell in NO_IN_CELLS:
                first_ref = _to_date(b["cell_out_logged_date"].get(cell))
            else:
                first_ref = _to_date(b["cell_in_logged_date"].get(cell))

            if cell_out >= planned_qty:
                last_out_ref = _to_date(b["cell_out_last_logged_date"].get(cell))
                days = (last_out_ref - first_ref).days if (first_ref and last_out_ref) else None
            else:
                days = (today - first_ref).days if first_ref else None

            cells[cell] = {
                "in":         cell_in,
                "out":        cell_out,
                "cum_out":    cell_out_cum,
                "cum_in":     cell_in_cum,
                "pending_in": pending_in,
                "actual_wip": actual_wip,
                "mtd":        cell_out_mtd,
                "ytd":        cell_out_ytd,
                "wip":        wip,
                "pct":        pct,
                "days":       days,
                # False for cells absent from the Cut Kit operation map —
                # lets the frontend skip them in its own WIP calculation.
                "applicable": (i == 0) or (cell in applicable_cells),
            }

        # ── Patch cum_out for non-applicable cells ─────────────────────────
        # The JS computes WIP as: prev_cell.cum_out − current_cell.cum_out
        # For a non-applicable cell (e.g. EMBROIDERY not in any WO's operation map),
        # its real cum_out is 0, so the JS would show WIP = SEWING.cum_out − 0 = large number.
        # Fix: set cum_out of each non-applicable cell to its nearest applicable
        # predecessor's cum_out, so JS yields 0 for that cell and the next
        # applicable cell (PRODUCTION) gets the correct value.
        for i, cell in enumerate(CELL_ORDER):
            if i == 0 or cell in applicable_cells:
                continue
            for j in range(i - 1, -1, -1):
                pred = CELL_ORDER[j]
                if pred in applicable_cells or j == 0:
                    cells[cell]["cum_out"] = cells[pred]["cum_out"]
                    break

        # ── Lead Days ──────────────────────────────────────────────────────
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

        completion_pct = round((packing_out / order_qty) * 100, 1) if order_qty else 0.0

        delivery_date = ""
        if b["delivery_date"]:
            delivery_date = formatdate(b["delivery_date"], "dd-mm-yyyy")

        if completion_pct >= 105:
            continue

        if cells["KNITTING"]["in"] == 0 and cells["KNITTING"]["out"] == 0:
            if (b["knitting_shift1_mtd"] + b["knitting_shift2_mtd"]) == 0:
                # Keep styles where knitting is done but downstream cells still have WIP
                has_downstream_wip = any(
                    b["cell_out_cum"].get(cell, 0) > 0
                    for cell in CELL_ORDER
                    if cell != "KNITTING"
                )
                if not has_downstream_wip:
                    continue        

        result.append({
            "style":              style,
            "buyer":              buyer,
            "colour":             colour,
            "season":             season,
            "delivery_date":      delivery_date,
            "order_qty":          order_qty,
            "planned_qty":        planned_qty,
            "cells":              cells,
            "completion_pct":     completion_pct,
            "lead_days":          lead_days,
            "knitting_shift1":    b["knitting_shift1"],
            "knitting_shift2":    b["knitting_shift2"],
            "knitting_shift1_mtd": b["knitting_shift1_mtd"],
            "knitting_shift2_mtd": b["knitting_shift2_mtd"],
            "knitting_shift1_ytd": b["knitting_shift1_ytd"],
            "knitting_shift2_ytd": b["knitting_shift2_ytd"],
            "knitting_shift1_cum": b["knitting_shift1_cum"],
            "knitting_shift2_cum": b["knitting_shift2_cum"],
            "knitting_wastage":   0,
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


def _get_knitting_shift_map_for_period(shift=1, date_condition="1=1", params=None):
    """
    Returns total scanned qty per (style, colour, size) for KNITTING by shift,
    filtered to the given date_condition.
      Shift 1: 10:00 AM – 20:00 (8 PM)
      Shift 2: 20:00 (8 PM) – next day 10:00 AM
    """
    if params is None:
        params = {}

    if shift == 1:
        time_condition = "TIME(isl.logged_time) >= '10:00:00' AND TIME(isl.logged_time) < '20:00:00'"
    else:
        time_condition = "(TIME(isl.logged_time) >= '20:00:00' OR TIME(isl.logged_time) < '10:00:00')"

    sql_query = f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            COALESCE(SUM(pi.quantity), 0)               AS qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi      ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor      ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc                                   ON tbc.parent = tor.name
                                               AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc        ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc   ON tc.name = pi.component
                                               AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                               ON pcflo.parent = tbc.work_order
                                               AND pcflo.physical_cell = pc.name
        WHERE pc.cell_name = 'KNITTING'
          AND isl.log_status = 'Completed'
          AND {date_condition}
          AND {time_condition}
          AND isl.operation = pcflo.last_operation
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """
    rows = frappe.db.sql(sql_query, params, as_dict=True) if params else frappe.db.sql(sql_query, as_dict=True)

    return {(r.style, r.colour, r.size): int(r.qty) for r in rows}


def _get_cell_op_map_for_period(op_type="last", date_condition="1=1", params=None):
    """
    Returns qty per (style, colour, size, cell_name) for either
    the first or last operation of each physical cell,
    filtered to the given date_condition.
    """
    if params is None:
        params = {}

    op_field         = "first_operation" if op_type == "first" else "last_operation"
    mending_op       = "MENDING IN"      if op_type == "first" else "MENDING OUT"
    cell_list        = ", ".join([f"'{c}'" for c in CELL_ORDER])

    sql_query = f"""
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
          AND {date_condition}
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """
    rows = frappe.db.sql(sql_query, params, as_dict=True) if params else frappe.db.sql(sql_query, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): int(r.qty) for r in rows}


def _get_cell_first_logged_date_map(op_type="first"):
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


def _get_applicable_cells_map():
    """
    Returns a dict keyed by (style, colour, size) whose value is the set of
    cell_names that have at least one configured operation in the Cut Kit
    operation map (tabPhysical Cell First and Last Operation).

    This drives the WIP / pending-in logic: cells that are NOT in the map for
    a particular SKU are non-applicable and their WIP is rendered as N/A rather
    than as a misleading zero.

    KNITTING is intentionally excluded here — the caller always adds it, because
    KNITTING is tracked via shift maps rather than via pcflo rows.
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


def _get_cell_last_logged_date_map():
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