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
    if not date:
        date = _date.today().isoformat()

    order_map = _get_order_map()
    if not order_map:
        return []

    applicable_cells_map  = _get_applicable_cells_map()
    outsourced_cells_map  = _get_outsourced_cells_map()
    cell_sequence_map     = _get_cell_sequence_map()

    cell_maps       = _get_cell_all_periods(date)
    knitting_maps   = _get_knitting_all_periods(date)
    cell_date_maps  = _get_cell_date_maps()
    rejection_maps  = _get_rejection_map(date)   # now returns {"daily": ..., "cum": ...}
    knitting_logged_time_map = _get_knitting_first_logged_time_map()
    logged_time_map          = _get_min_logged_time_map()

    # Unpack cell maps
    cell_in_map      = cell_maps["daily_in"]
    cell_out_map     = cell_maps["daily_out"]
    cell_in_cum_map  = cell_maps["cum_in"]
    cell_out_cum_map = cell_maps["cum_out"]
    cell_out_mtd_map = cell_maps["mtd_out"]
    cell_out_ytd_map = cell_maps["ytd_out"]

    # Unpack knitting maps
    knitting_shift1_map     = knitting_maps["daily_s1"]
    knitting_shift2_map     = knitting_maps["daily_s2"]
    knitting_shift1_cum_map = knitting_maps["cum_s1"]
    knitting_shift2_cum_map = knitting_maps["cum_s2"]
    knitting_shift1_mtd     = knitting_maps["mtd_s1"]
    knitting_shift2_mtd     = knitting_maps["mtd_s2"]
    knitting_shift1_ytd     = knitting_maps["ytd_s1"]
    knitting_shift2_ytd     = knitting_maps["ytd_s2"]

    # Unpack date maps
    cell_in_logged_date_map       = cell_date_maps["first_in"]
    cell_out_logged_date_map      = cell_date_maps["first_out"]
    cell_out_last_logged_date_map = cell_date_maps["last_out"]

    # Unpack rejection maps (daily and cumulative)
    rejection_map     = rejection_maps["daily"]
    rejection_cum_map = rejection_maps["cum"]

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
        "cell_rejection":              defaultdict(int),
        "cell_rejection_cum":          defaultdict(int),
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
        "knitting_rejection":          0,
        "knitting_rejection_cum":      0,
        "applicable_cells":            set(),
        "outsourced_cells":            set(),
        "cell_sequence":               [],    # ordered list of cells per actual route
    })

    for (style, colour, size), info in order_map.items():
        key = (info.buyer or "", info.season or "", style, colour)
        agg[key]["order_qty"]   += int(info.order_qty or 0)
        agg[key]["planned_qty"] += int(info.planned_qty or 0)

        sku_cells = applicable_cells_map.get((style, colour, size), set())
        agg[key]["applicable_cells"] |= sku_cells
        agg[key]["applicable_cells"].add("KNITTING")

        # Union outsourced cells across all sizes for this style/colour group.
        sku_outsourced = outsourced_cells_map.get((style, colour, size), set())
        agg[key]["outsourced_cells"] |= sku_outsourced

        # Merge per-SKU cell sequence into the group sequence.
        if not agg[key]["cell_sequence"]:
            sku_seq = cell_sequence_map.get((style, colour, size), [])
            if sku_seq:
                agg[key]["cell_sequence"] = sku_seq

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
            agg[key]["cell_in"][cell]            += cell_in_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out"][cell]           += cell_out_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out_mtd"][cell]       += cell_out_mtd_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out_ytd"][cell]       += cell_out_ytd_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out_cum"][cell]       += cell_out_cum_map.get((style, colour, size, cell), 0)
            agg[key]["cell_in_cum"][cell]        += cell_in_cum_map.get((style, colour, size, cell), 0)
            agg[key]["cell_rejection"][cell]     += rejection_map.get((style, colour, size, cell), 0)
            agg[key]["cell_rejection_cum"][cell] += rejection_cum_map.get((style, colour, size, cell), 0)

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

        agg[key]["knitting_shift1"]     += knitting_shift1_map.get((style, colour, size), 0)
        agg[key]["knitting_shift2"]     += knitting_shift2_map.get((style, colour, size), 0)
        agg[key]["knitting_shift1_mtd"] += knitting_shift1_mtd.get((style, colour, size), 0)
        agg[key]["knitting_shift2_mtd"] += knitting_shift2_mtd.get((style, colour, size), 0)
        agg[key]["knitting_shift1_ytd"] += knitting_shift1_ytd.get((style, colour, size), 0)
        agg[key]["knitting_shift2_ytd"] += knitting_shift2_ytd.get((style, colour, size), 0)
        agg[key]["knitting_shift1_cum"] += knitting_shift1_cum_map.get((style, colour, size), 0)
        agg[key]["knitting_shift2_cum"] += knitting_shift2_cum_map.get((style, colour, size), 0)
        # Knitting rejection = KNITTING cell rejection (already in cell_rejection)
        agg[key]["knitting_rejection"]     += rejection_map.get((style, colour, size, "KNITTING"), 0)
        agg[key]["knitting_rejection_cum"] += rejection_cum_map.get((style, colour, size, "KNITTING"), 0)

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

        knitting_cum     = b["knitting_shift1_cum"] + b["knitting_shift2_cum"]
        applicable_cells = b["applicable_cells"] or set(CELL_ORDER)
        outsourced_cells = b["outsourced_cells"]

        # Use the actual per-style cell sequence from the work order route.
        route = b["cell_sequence"] or CELL_ORDER
        if route and route[0] != "KNITTING":
            route = ["KNITTING"] + [c for c in route if c != "KNITTING"]

        cells = {}

        # ── WIP chain state ───────────────────────────────────────────────
        prev_out_cum = 0

        for i, cell in enumerate(route):
            cell_in          = b["cell_in"].get(cell, 0)
            cell_out         = b["cell_out"].get(cell, 0)
            cell_out_mtd     = b["cell_out_mtd"].get(cell, 0)
            cell_out_ytd     = b["cell_out_ytd"].get(cell, 0)
            cell_out_cum     = knitting_cum if cell == "KNITTING" else b["cell_out_cum"].get(cell, 0)
            cell_in_cum      = b["cell_in_cum"].get(cell, 0)
            cell_rej         = b["cell_rejection"].get(cell, 0)
            cell_rej_cum     = b["cell_rejection_cum"].get(cell, 0)
            pct              = round((cell_out / order_qty) * 100) if order_qty else 0

            is_outsourced = cell in outsourced_cells

            if i == 0:
                # KNITTING — first cell, no WIP concept
                actual_wip = None
                pending_in = None
                prev_out_cum = knitting_cum

            elif cell not in applicable_cells:
                actual_wip = None
                pending_in = None

            elif is_outsourced:
                actual_wip = 0
                pending_in = 0

            else:
                actual_wip   = max(0, cell_in_cum - cell_out_cum)
                pending_in   = max(0, prev_out_cum - cell_in_cum)
                prev_out_cum = cell_out_cum

            wip = actual_wip

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
                "in":            cell_in,
                "out":           cell_out,
                "cum_out":       cell_out_cum,
                "cum_in":        cell_in_cum,
                "pending_in":    pending_in,
                "actual_wip":    actual_wip,
                "mtd":           cell_out_mtd,
                "ytd":           cell_out_ytd,
                "wip":           wip,
                "pct":           pct,
                "days":          days,
                "applicable":    (i == 0) or (cell in applicable_cells),
                "is_outsourced": is_outsourced,
                "rejection":     cell_rej,
                "rejection_cum": cell_rej_cum,
            }

        # Ensure all CELL_ORDER cells exist in the dict
        for cell in CELL_ORDER:
            if cell not in cells:
                cells[cell] = {
                    "in": 0, "out": 0, "cum_out": 0, "cum_in": 0,
                    "pending_in": None, "actual_wip": None,
                    "mtd": 0, "ytd": 0, "wip": None, "pct": 0,
                    "days": None, "applicable": False, "is_outsourced": False,
                    "rejection": 0, "rejection_cum": 0,
                }

        # Patch cum_out for non-applicable cells
        for i, cell in enumerate(route):
            if i == 0 or cell in applicable_cells:
                continue
            for j in range(i - 1, -1, -1):
                pred = route[j]
                if pred in applicable_cells or j == 0:
                    cells[cell]["cum_out"] = cells[pred]["cum_out"]
                    break

        # Lead Days
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
                has_downstream_wip = any(
                    b["cell_out_cum"].get(cell, 0) > 0
                    for cell in CELL_ORDER
                    if cell != "KNITTING"
                )
                if not has_downstream_wip:
                    continue

        result.append({
            "style":               style,
            "buyer":               buyer,
            "colour":              colour,
            "season":              season,
            "delivery_date":       delivery_date,
            "order_qty":           order_qty,
            "planned_qty":         planned_qty,
            "cells":               cells,
            "completion_pct":      completion_pct,
            "lead_days":           lead_days,
            "knitting_shift1":     b["knitting_shift1"],
            "knitting_shift2":     b["knitting_shift2"],
            "knitting_shift1_mtd": b["knitting_shift1_mtd"],
            "knitting_shift2_mtd": b["knitting_shift2_mtd"],
            "knitting_shift1_ytd": b["knitting_shift1_ytd"],
            "knitting_shift2_ytd": b["knitting_shift2_ytd"],
            "knitting_shift1_cum": b["knitting_shift1_cum"],
            "knitting_shift2_cum": b["knitting_shift2_cum"],
            "knitting_wastage":    0,
            "knitting_rejection":      b["knitting_rejection"],
            "knitting_rejection_cum":  b["knitting_rejection_cum"],
        })

    return result


# ── Optimised helpers ─────────────────────────────────────────────────────────

def _get_cell_all_periods(date):
    """
    Replaces 6 separate _get_cell_op_map_for_period calls with one query.
    Returns all six maps in a single dict using conditional SUM aggregation:
      daily_in, daily_out   — first/last operation scans on `date`
      cum_in,   cum_out     — first/last operation scans all time
      mtd_out               — last operation scans month-to-date
      ytd_out               — last operation scans year-to-date
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            pc.cell_name             AS cell_name,

            -- ── daily IN (first_operation, selected date) ──────────────
            COALESCE(SUM(
                CASE WHEN DATE(isl.logged_time) = %(date)s
                      AND isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING IN'
                            ELSE pcflo.first_operation END
                THEN pi.quantity ELSE 0 END
            ), 0) AS daily_in,

            -- ── daily OUT (last_operation, selected date) ──────────────
            COALESCE(SUM(
                CASE WHEN DATE(isl.logged_time) = %(date)s
                      AND isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT'
                            ELSE pcflo.last_operation END
                THEN pi.quantity ELSE 0 END
            ), 0) AS daily_out,

            -- ── cumulative IN (first_operation, all time) ──────────────
            COALESCE(SUM(
                CASE WHEN isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING IN'
                            ELSE pcflo.first_operation END
                THEN pi.quantity ELSE 0 END
            ), 0) AS cum_in,

            -- ── cumulative OUT (last_operation, all time) ──────────────
            COALESCE(SUM(
                CASE WHEN isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT'
                            ELSE pcflo.last_operation END
                THEN pi.quantity ELSE 0 END
            ), 0) AS cum_out,

            -- ── MTD OUT (last_operation, month-to-date) ────────────────
            COALESCE(SUM(
                CASE WHEN YEAR(isl.logged_time)  = YEAR(%(date)s)
                      AND MONTH(isl.logged_time) = MONTH(%(date)s)
                      AND DATE(isl.logged_time) <= %(date)s
                      AND isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT'
                            ELSE pcflo.last_operation END
                THEN pi.quantity ELSE 0 END
            ), 0) AS mtd_out,

            -- ── YTD OUT (last_operation, year-to-date) ─────────────────
            COALESCE(SUM(
                CASE WHEN YEAR(isl.logged_time) = YEAR(%(date)s)
                      AND DATE(isl.logged_time) <= %(date)s
                      AND isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT'
                            ELSE pcflo.last_operation END
                THEN pi.quantity ELSE 0 END
            ), 0) AS ytd_out

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
        WHERE isl.log_status = 'Completed'
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, {"date": date}, as_dict=True)

    daily_in  = {}
    daily_out = {}
    cum_in    = {}
    cum_out   = {}
    mtd_out   = {}
    ytd_out   = {}

    for r in rows:
        k = (r.style, r.colour, r.size, r.cell_name)
        daily_in[k]  = int(r.daily_in  or 0)
        daily_out[k] = int(r.daily_out or 0)
        cum_in[k]    = int(r.cum_in    or 0)
        cum_out[k]   = int(r.cum_out   or 0)
        mtd_out[k]   = int(r.mtd_out   or 0)
        ytd_out[k]   = int(r.ytd_out   or 0)

    return {
        "daily_in":  daily_in,
        "daily_out": daily_out,
        "cum_in":    cum_in,
        "cum_out":   cum_out,
        "mtd_out":   mtd_out,
        "ytd_out":   ytd_out,
    }


def _get_knitting_all_periods(date):
    """
    Replaces 8 separate _get_knitting_shift_map_for_period calls with one query.
    Returns daily/cum/mtd/ytd × shift1/shift2 in a single dict.

    Shift 1: 10:00–20:00   Shift 2: 20:00–10:00 (next day)
    """
    rows = frappe.db.sql("""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,

            -- ── daily shift 1 ──────────────────────────────────────────
            COALESCE(SUM(
                CASE WHEN DATE(isl.logged_time) = %(date)s
                      AND TIME(isl.logged_time) >= '10:00:00'
                      AND TIME(isl.logged_time) <  '20:00:00'
                THEN pi.quantity ELSE 0 END
            ), 0) AS daily_s1,

            -- ── daily shift 2 ──────────────────────────────────────────
            COALESCE(SUM(
                CASE WHEN DATE(isl.logged_time) = %(date)s
                      AND (TIME(isl.logged_time) >= '20:00:00'
                           OR TIME(isl.logged_time) < '10:00:00')
                THEN pi.quantity ELSE 0 END
            ), 0) AS daily_s2,

            -- ── cumulative shift 1 (all time) ──────────────────────────
            COALESCE(SUM(
                CASE WHEN TIME(isl.logged_time) >= '10:00:00'
                      AND TIME(isl.logged_time) <  '20:00:00'
                THEN pi.quantity ELSE 0 END
            ), 0) AS cum_s1,

            -- ── cumulative shift 2 (all time) ──────────────────────────
            COALESCE(SUM(
                CASE WHEN TIME(isl.logged_time) >= '20:00:00'
                      OR  TIME(isl.logged_time) <  '10:00:00'
                THEN pi.quantity ELSE 0 END
            ), 0) AS cum_s2,

            -- ── MTD shift 1 ────────────────────────────────────────────
            COALESCE(SUM(
                CASE WHEN YEAR(isl.logged_time)  = YEAR(%(date)s)
                      AND MONTH(isl.logged_time) = MONTH(%(date)s)
                      AND DATE(isl.logged_time) <= %(date)s
                      AND TIME(isl.logged_time) >= '10:00:00'
                      AND TIME(isl.logged_time) <  '20:00:00'
                THEN pi.quantity ELSE 0 END
            ), 0) AS mtd_s1,

            -- ── MTD shift 2 ────────────────────────────────────────────
            COALESCE(SUM(
                CASE WHEN YEAR(isl.logged_time)  = YEAR(%(date)s)
                      AND MONTH(isl.logged_time) = MONTH(%(date)s)
                      AND DATE(isl.logged_time) <= %(date)s
                      AND (TIME(isl.logged_time) >= '20:00:00'
                           OR TIME(isl.logged_time) < '10:00:00')
                THEN pi.quantity ELSE 0 END
            ), 0) AS mtd_s2,

            -- ── YTD shift 1 ────────────────────────────────────────────
            COALESCE(SUM(
                CASE WHEN YEAR(isl.logged_time) = YEAR(%(date)s)
                      AND DATE(isl.logged_time) <= %(date)s
                      AND TIME(isl.logged_time) >= '10:00:00'
                      AND TIME(isl.logged_time) <  '20:00:00'
                THEN pi.quantity ELSE 0 END
            ), 0) AS ytd_s1,

            -- ── YTD shift 2 ────────────────────────────────────────────
            COALESCE(SUM(
                CASE WHEN YEAR(isl.logged_time) = YEAR(%(date)s)
                      AND DATE(isl.logged_time) <= %(date)s
                      AND (TIME(isl.logged_time) >= '20:00:00'
                           OR TIME(isl.logged_time) < '10:00:00')
                THEN pi.quantity ELSE 0 END
            ), 0) AS ytd_s2

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
        WHERE pc.cell_name = 'KNITTING'
          AND isl.log_status = 'Completed'
          AND isl.operation = pcflo.last_operation
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """, {"date": date}, as_dict=True)

    daily_s1 = {}; daily_s2 = {}
    cum_s1   = {}; cum_s2   = {}
    mtd_s1   = {}; mtd_s2   = {}
    ytd_s1   = {}; ytd_s2   = {}

    for r in rows:
        k = (r.style, r.colour, r.size)
        daily_s1[k] = int(r.daily_s1 or 0)
        daily_s2[k] = int(r.daily_s2 or 0)
        cum_s1[k]   = int(r.cum_s1   or 0)
        cum_s2[k]   = int(r.cum_s2   or 0)
        mtd_s1[k]   = int(r.mtd_s1   or 0)
        mtd_s2[k]   = int(r.mtd_s2   or 0)
        ytd_s1[k]   = int(r.ytd_s1   or 0)
        ytd_s2[k]   = int(r.ytd_s2   or 0)

    return {
        "daily_s1": daily_s1, "daily_s2": daily_s2,
        "cum_s1":   cum_s1,   "cum_s2":   cum_s2,
        "mtd_s1":   mtd_s1,   "mtd_s2":   mtd_s2,
        "ytd_s1":   ytd_s1,   "ytd_s2":   ytd_s2,
    }


def _get_cell_date_maps():
    """
    Returns first_in, first_out, last_out date maps per (style, colour, size, cell).
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            pc.cell_name             AS cell_name,

            MIN(CASE WHEN isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING IN'
                            ELSE pcflo.first_operation END
                THEN isl.logged_time ELSE NULL END) AS first_in,

            MIN(CASE WHEN isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT'
                            ELSE pcflo.last_operation END
                THEN isl.logged_time ELSE NULL END) AS first_out,

            MAX(CASE WHEN isl.operation = CASE
                            WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT'
                            ELSE pcflo.last_operation END
                THEN isl.logged_time ELSE NULL END) AS last_out

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
        WHERE isl.log_status = 'Completed'
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, as_dict=True)

    first_in  = {}
    first_out = {}
    last_out  = {}

    for r in rows:
        k = (r.style, r.colour, r.size, r.cell_name)
        if r.first_in:
            first_in[k]  = r.first_in
        if r.first_out:
            first_out[k] = r.first_out
        if r.last_out:
            last_out[k]  = r.last_out

    return {"first_in": first_in, "first_out": first_out, "last_out": last_out}


def _get_rejection_map(date):
    """
    Returns rejection counts per (style, colour, size, cell_name) in two buckets:
      "daily" — scans on `date` only
      "cum"   — all-time cumulative (no date filter)

    Rejected statuses: QC Rework, QC Reject, SP Rework, SP Reject.
    No log_status / operation filter — rejection scans may not share the
    same operation path as normal production scans.
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            pc.cell_name             AS cell_name,

            -- daily: only the selected date
            COUNT(CASE WHEN DATE(isl.logged_time) = %(date)s THEN 1 END)
                AS daily_rejection_count,

            -- cumulative: all time
            COUNT(*)
                AS cum_rejection_count

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
        WHERE isl.log_status = 'Completed'
          AND isl.status IN ('QC Rework', 'QC Reject', 'SP Rework', 'SP Reject')
          AND pc.cell_name IN ({cell_list})
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, {"date": date}, as_dict=True)

    daily = {}
    cum   = {}
    for r in rows:
        k        = (r.style, r.colour, r.size, r.cell_name)
        daily[k] = int(r.daily_rejection_count or 0)
        cum[k]   = int(r.cum_rejection_count   or 0)

    return {"daily": daily, "cum": cum}


# ── Unchanged helpers ─────────────────────────────────────────────────────────

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


def _get_applicable_cells_map():
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
    Returns {(style, colour, size) -> set(cell_names)} for cells where
    any operation is marked production_type = 'Outsourced' in the
    Cut Kit Operations child table (parentfield = 'custom_operations_list').
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
                                                AND cko.parentfield = 'custom_operations_list'
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                 ON pcflo.parent = tbc.work_order
                                                AND (
                                                    pcflo.first_operation = cko.operation
                                                    OR pcflo.last_operation = cko.operation
                                                )
        INNER JOIN `tabPhysical Cell` pc         ON pc.name = pcflo.physical_cell
        WHERE tbc.parentfield = 'bundle_configurations'
          AND cko.production_type = 'Outsourced'
          AND pc.cell_name IN ({cell_list})
    """, as_dict=True)

    result = defaultdict(set)
    for r in rows:
        result[(r.style, r.colour, r.size)].add(r.cell_name)
    return result


def _get_cell_sequence_map():
    """
    Returns {(style, colour, size) → [cell_name, ...]} where the list is the
    actual ordered sequence of physical cells for that SKU, derived from
    tabCut Kit Operations ordered by idx.
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])
    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            pc.cell_name             AS cell_name,
            MIN(cko.idx)             AS min_idx
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor       ON tor.name = tbc.parent
        INNER JOIN `tabItem` itm                 ON itm.name = tor.item
        INNER JOIN `tabCut Kit Operations` cko   ON cko.parent     = tbc.work_order
                                                AND cko.parentfield = 'custom_operations_list'
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                 ON pcflo.parent = tbc.work_order
                                                AND (
                                                    pcflo.first_operation = cko.operation
                                                    OR pcflo.last_operation = cko.operation
                                                )
        INNER JOIN `tabPhysical Cell` pc         ON pc.name = pcflo.physical_cell
        WHERE tbc.parentfield = 'bundle_configurations'
          AND pc.cell_name IN ({cell_list})
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
        ORDER BY itm.custom_style_master, itm.custom_colour_name, tbc.size, min_idx
    """, as_dict=True)

    result = {}
    for r in rows:
        key = (r.style, r.colour, r.size)
        if key not in result:
            result[key] = []
        if r.cell_name not in result[key]:
            result[key].append(r.cell_name)
    return result