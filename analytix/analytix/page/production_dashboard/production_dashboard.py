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

    cell_in_map   = _get_cell_op_map(op_type="first")
    cell_out_map  = _get_cell_op_map(op_type="last")

    cell_in_logged_date_map       = _get_cell_first_logged_date_map(op_type="first")
    cell_out_logged_date_map      = _get_cell_first_logged_date_map(op_type="last")
    cell_out_last_logged_date_map = _get_cell_last_logged_date_map()

    knitting_logged_time_map = _get_knitting_first_logged_time_map()
    logged_time_map          = _get_min_logged_time_map()
    outsourced_cells_map     = _get_outsourced_cells_map()
    rejection_map            = _get_rejection_map()

    # ── Aggregate at (buyer, season, style, colour) across all sizes ──────
    agg = defaultdict(lambda: {
        "order_qty":                   0,
        "planned_qty":                 0,
        "delivery_date":               None,
        "min_logged_time":             None,
        "rej_qty":                     0,
        "cell_in":                     defaultdict(int),
        "cell_out":                    defaultdict(int),
        "cell_in_logged_date":         {},
        "cell_out_logged_date":        {},
        "cell_out_last_logged_date":   {},
        "knitting_first_logged":       None,
        "outsourced_cells":            set(),
    })

    for (style, colour, size), info in order_map.items():
        key = (info.buyer or "", info.season or "", style, colour)
        agg[key]["order_qty"]   += int(info.order_qty or 0)
        agg[key]["planned_qty"] += int(info.planned_qty or 0)

        d = info.delivery_date
        if d and (agg[key]["delivery_date"] is None or d > agg[key]["delivery_date"]):
            agg[key]["delivery_date"] = d

        lt = logged_time_map.get((style, colour, size))
        if lt and (agg[key]["min_logged_time"] is None or lt < agg[key]["min_logged_time"]):
            agg[key]["min_logged_time"] = lt

        klt = knitting_logged_time_map.get((style, colour, size))
        if klt and (agg[key]["knitting_first_logged"] is None or klt < agg[key]["knitting_first_logged"]):
            agg[key]["knitting_first_logged"] = klt

        agg[key]["outsourced_cells"] |= outsourced_cells_map.get((style, colour, size), set())

        # Sum rejections across all cells for this (style, colour, size)
        for cell in CELL_ORDER:
            agg[key]["rej_qty"] += rejection_map.get((style, colour, size, cell), 0)

        for cell in CELL_ORDER:
            agg[key]["cell_in"][cell]  += cell_in_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out"][cell] += cell_out_map.get((style, colour, size, cell), 0)

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
        """Convert datetime / date / str to date, or return None."""
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

        order_qty        = b["order_qty"]
        planned_qty      = b["planned_qty"]
        outsourced_cells = b["outsourced_cells"]

        cells = {}
        for cell in CELL_ORDER:
            cell_in       = b["cell_in"].get(cell, 0)
            cell_out      = b["cell_out"].get(cell, 0)
            pct           = round((cell_out / order_qty) * 100) if order_qty else 0
            is_outsourced = cell in outsourced_cells

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
                "pct":           pct,
                "days":          days,
                "is_outsourced": is_outsourced,
            }

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

        # Hide styles where packing out + total rejections >= planned qty
        if (packing_out + b["rej_qty"]) >= planned_qty:
            continue

        if cells["KNITTING"]["in"] == 0:
            continue

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


def _get_cell_op_map(op_type="last"):
    op_field   = "first_operation" if op_type == "first" else "last_operation"
    mending_op = "MENDING IN"      if op_type == "first" else "MENDING OUT"
    cell_list  = ", ".join([f"'{c}'" for c in CELL_ORDER])

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
    any operation is marked production_type = 'Outsourced' in the
    Cut Kit Operations child table (parentfield = 'custom_operations_list').

    Path: cko.operation → pcflo.first_operation OR pcflo.last_operation
          → pcflo.physical_cell → pc.cell_name
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
          AND cko.production_type = 'Outsourced'
          AND pc.cell_name IN ({cell_list})
    """, as_dict=True)

    result = defaultdict(set)
    for r in rows:
        result[(r.style, r.colour, r.size)].add(r.cell_name)
    return result


def _get_rejection_map():
    """
    Returns cumulative rejection counts per (style, colour, size, cell_name).

    Rejected statuses: QC Rejected, SP Rejected.
    QC Rework / SP Rework are rework loops where pieces re-enter the line —
    including them would double-count and inflate the figure. Only permanent
    rejects are counted here.
    """
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master       AS style,
            itm.custom_colour_name        AS colour,
            tbc.size                      AS size,
            pc.cell_name                  AS cell_name,
            COALESCE(SUM(pi.quantity), 0) AS rejection_count
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi
            ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor
            ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
            ON tbc.name   = pi.bundle_configuration
            AND tbc.parent = tor.name
        INNER JOIN `tabItem` itm
            ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc
            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc
            ON tc.name = pi.component AND tc.is_main = 1
        WHERE isl.log_status = 'Completed'
          AND isl.status IN ('QC Rejected', 'SP Rejected')
          AND pc.cell_name IN ({cell_list})
        GROUP BY
            itm.custom_style_master,
            itm.custom_colour_name,
            tbc.size,
            pc.cell_name
    """, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): int(r.rejection_count or 0) for r in rows}


def _get_cell_sequence_map():
    """
    Returns {(style, colour, size) → [cell_name, ...]} where the list is the
    actual ordered sequence of physical cells for that SKU, derived from
    tabCut Kit Operations ordered by idx.

    Multiple operations belonging to the same physical cell collapse to a
    single entry (order-preserving dedup) — what matters for WIP chain
    calculation is the cell sequence, not individual operations.

    This replaces the hardcoded CELL_ORDER walk in get_style_sizewise_data
    so that non-standard routes (e.g. CUTTING → EMBROIDERY → LINKING instead
    of CUTTING → LINKING → EMBROIDERY) get correct WIP attribution.
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
      - Cell iteration follows the actual per-style route from
        tabCut Kit Operations (ordered by idx) rather than the hardcoded
        CELL_ORDER, so non-standard routes (e.g. CUTTING → EMBROIDERY →
        LINKING) get correct WIP attribution.
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
    outsourced_cells_map = _get_outsourced_cells_map()
    outsourced_cells = set()
    for size in sizes_info:
        outsourced_cells |= outsourced_cells_map.get((style, colour, size), set())

    # ── Actual per-style cell sequence (from tabCut Kit Operations idx) ───
    # Falls back to CELL_ORDER if no sequence found.
    # KNITTING is always prepended as the first cell if not already present.
    cell_sequence_map = _get_cell_sequence_map()
    route = []
    for size in sizes_info:
        seq = cell_sequence_map.get((style, colour, size), [])
        if seq:
            route = seq
            break
    if not route:
        route = list(CELL_ORDER)
    if route[0] != "KNITTING":
        route = ["KNITTING"] + [c for c in route if c != "KNITTING"]

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

    # Organise into {(size, cell): {"in": qty, "out": qty}}
    scan_map = defaultdict(lambda: {"in": 0, "out": 0})
    for r in scan_rows:
        key = (r.size, r.cell_name)
        if r.cell_name == "MENDING":
            if r.operation == "MENDING IN":
                scan_map[key]["in"]  += int(r.qty)
            if r.operation == "MENDING OUT":
                scan_map[key]["out"] += int(r.qty)
        else:
            if r.operation == r.first_op:
                scan_map[key]["in"]  += int(r.qty)
            if r.operation == r.last_op:
                scan_map[key]["out"] += int(r.qty)

    # ── Build per-cell rows using actual route order ───────────────────────
    prev_total_out = 0
    cell_rows = []

    for cell in route:
        if cell not in applicable_cells:
            continue

        is_outsourced = cell in outsourced_cells

        in_by_size  = {}
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
            wip_pending = 0
            wip_actual  = 0
            # Do NOT advance prev_total_out
        else:
            wip_pending    = max(0, prev_total_out - total_in)
            wip_actual     = max(0, total_in - total_out)
            prev_total_out = total_out

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