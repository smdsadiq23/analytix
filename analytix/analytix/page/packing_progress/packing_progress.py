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

# Cells that have only an OUT operation — no IN scan exists by design.
# These must never be treated as N/A just because cell_in = 0.
NO_IN_CELLS = {"KNITTING", "PRODUCTION", "FINAL CHECK"}


@frappe.whitelist()
def get_packing_progress_data():
    """
    Returns one row per (buyer, season, style, colour) for the Packing Progress
    dashboard.

    Filtering rules:
      1. Only styles where PACKING IN > 0 (packing has started).
      2. Hide styles where packing_out >= planned_qty (fully packed).
      3. Outsourced cells are flagged with is_outsourced=True so the JS can
         render them as "OS" and exclude them from the total pending sum.

    Each cell dict contains:
      in            — cumulative qty that completed the first operation of the cell
                      (always 0 for no_in cells — only OUT matters for those)
      out           — cumulative qty that completed the last operation of the cell
      rej           — cumulative rejection qty for this cell (QC Reject + SP Reject)
                      subtracted from pending so rejected units don't inflate counts
      is_outsourced — True if this cell is outsourced for this style
      no_in         — True if this cell has no IN operation by design
                      (KNITTING, PRODUCTION, FINAL CHECK) so the JS pending
                      logic never treats them as N/A based on inn===0 alone
    """
    order_map            = _get_order_map()
    if not order_map:
        return []

    cell_in_map          = _get_cell_op_map(op_type="first")
    cell_out_map         = _get_cell_op_map(op_type="last")
    outsourced_cells_map = _get_outsourced_cells_map()
    logged_time_map      = _get_min_logged_time_map()
    rejection_map        = _get_rejection_map()

    # ── Aggregate at (buyer, season, style, colour) across all sizes ──────
    agg = defaultdict(lambda: {
        "order_qty":        0,
        "planned_qty":      0,
        "delivery_date":    None,
        "min_logged_time":  None,
        "rej_qty":          0,
        "cell_in":          defaultdict(int),
        "cell_out":         defaultdict(int),
        "cell_rej":         defaultdict(int),   # per-cell rejection totals
        "outsourced_cells": set(),
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

        agg[key]["outsourced_cells"] |= outsourced_cells_map.get((style, colour, size), set())

        # Sum rejections across all cells for this (style, colour, size)
        # and also track per-cell so JS can subtract from pending
        for cell in CELL_ORDER:
            rej = rejection_map.get((style, colour, size, cell), 0)
            agg[key]["rej_qty"]        += rej
            agg[key]["cell_rej"][cell] += rej

        for cell in CELL_ORDER:
            agg[key]["cell_in"][cell]  += cell_in_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out"][cell] += cell_out_map.get((style, colour, size, cell), 0)

    # ── Build result rows ─────────────────────────────────────────────────
    result = []

    sorted_keys = sorted(
        agg.keys(),
        key=lambda k: (
            agg[k]["min_logged_time"] is None,
            agg[k]["min_logged_time"] or "0000-00-00 00:00:00",
        )
    )

    for buyer, season, style, colour in sorted_keys:
        b = agg[(buyer, season, style, colour)]

        order_qty        = b["order_qty"]
        planned_qty      = b["planned_qty"]
        outsourced_cells = b["outsourced_cells"]

        packing_in  = b["cell_in"].get("PACKING", 0)
        packing_out = b["cell_out"].get("PACKING", 0)

        # ── Filter 1: skip styles where packing has not started ───────────
        if packing_in == 0:
            continue

        # ── Filter 2: skip styles that are fully packed ───────────────────
        if packing_out >= planned_qty:
            continue

        # ── Build per-cell data ───────────────────────────────────────────
        cells = {}
        for cell in CELL_ORDER:
            cells[cell] = {
                "in":            b["cell_in"].get(cell, 0),
                "out":           b["cell_out"].get(cell, 0),
                "rej":           b["cell_rej"].get(cell, 0),   # per-cell rejections
                "is_outsourced": cell in outsourced_cells,
                "no_in":         cell in NO_IN_CELLS,
            }

        delivery_date = ""
        if b["delivery_date"]:
            delivery_date = formatdate(b["delivery_date"], "dd-mm-yyyy")

        first_scan_date = ""
        if b["min_logged_time"]:
            first_scan_date = formatdate(b["min_logged_time"], "dd-mm-yyyy")

        result.append({
            "style":           style,
            "buyer":           buyer,
            "colour":          colour,
            "season":          season,
            "delivery_date":   delivery_date,
            "order_qty":       order_qty,
            "planned_qty":     planned_qty,
            "rej_qty":         b["rej_qty"],
            "cells":           cells,
            "first_scan_date": first_scan_date,
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
        INNER JOIN `tabSales Order Item` soi    ON soi.parent = so.name
                                               AND soi.custom_size = tbc.size
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
        INNER JOIN `tabProduction Item` pi  ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor  ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc                               ON tbc.parent = tor.name
                                           AND tbc.size   = pi.size
        INNER JOIN `tabItem` itm            ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc    ON pc.name = isl.physical_cell
                                           AND pc.cell_name = 'PACKING'
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                            ON pcflo.parent        = tbc.work_order
                                           AND pcflo.physical_cell  = pc.name
        WHERE isl.log_status = 'Completed'
          AND isl.operation  = pcflo.first_operation
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """, as_dict=True)
    return {(r.style, r.colour, r.size): r.min_logged_time for r in rows}


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
        ) tbc                                       ON tbc.parent = tor.name
                                                   AND tbc.size   = pi.size
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component
                                                   AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                   ON pcflo.parent       = tbc.work_order
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


def _get_outsourced_cells_map():
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
        WHERE tbc.parentfield  = 'bundle_configurations'
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

    Uses pi.bundle_configuration to join tbc directly (same pattern as the
    reference rejection query) and sums pi.quantity so we count actual
    garment units, not scan-log rows.

    Rejected statuses: QC Reject, SP Reject.
    QC Rework / SP Rework are rework loops where pieces re-enter the line —
    including them would double-count and inflate the figure. Only permanent
    rejects are counted here, consistent with the reference dashboard query.
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
          AND isl.status IN ('QC Reject', 'SP Reject')
          AND pc.cell_name IN ({cell_list})
        GROUP BY
            itm.custom_style_master,
            itm.custom_colour_name,
            tbc.size,
            pc.cell_name
    """, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): int(r.rejection_count or 0) for r in rows}