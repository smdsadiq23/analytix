# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import date, datetime


@frappe.whitelist()
def get_dashboard_data(date=None, today=None):
    """
    Returns:
        {
            "daily": [ ...rows with cells for the selected date... ],
            "mtd_output":  { "KNITTING": N, "MENDING": N, ... },
            "ytd_output":  { "KNITTING": N, "MENDING": N, ... },
        }

    'date'  – the date selected in the UI (daily input/output).
    'today' – the actual calendar date used to bound MTD/YTD windows.
              Falls back to server's today if not supplied.
    """
    selected_date = date or frappe.utils.today()
    anchor_today  = today or frappe.utils.today()

    # ── date boundaries ──────────────────────────────────────────────────────
    anchor_dt   = datetime.strptime(anchor_today, "%Y-%m-%d").date()
    month_start = anchor_dt.replace(day=1).strftime("%Y-%m-%d")
    year_start  = anchor_dt.replace(month=1, day=1).strftime("%Y-%m-%d")

    daily_rows  = _fetch_rows(selected_date, selected_date)
    mtd_rows    = _fetch_rows(month_start,   anchor_today)
    ytd_rows    = _fetch_rows(year_start,    anchor_today)

    mtd_output  = _aggregate_output(mtd_rows)
    ytd_output  = _aggregate_output(ytd_rows)

    return {
        "daily":      daily_rows,
        "mtd_output": mtd_output,
        "ytd_output": ytd_output,
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _fetch_rows(from_date, to_date):
    """
    Returns one dict per (sales_order, work_order, tracking_order, size) combo
    with a `cells` map:  { SECTION_KEY: { "in": N, "out": N } }
    and knitting-specific fields.
    """
    raw = frappe.db.sql(
        """
        SELECT
            tbc.sales_order,
            tbc.work_order,
            tor.name           AS tracking_order,
            tor.item           AS fg_item,
            pi.size,
            itm.brand,

            /* ── physical cell / operation type for bucketing ─────────── */
            UPPER(TRIM(COALESCE(isl.physical_cell, '')))   AS physical_cell,
            UPPER(TRIM(COALESCE(op.custom_operation_type, ''))) AS operation_type,

            /* ── in / out flags ─────────────────────────────────────────
               We treat every completed scan as OUTPUT for its section.
               INPUT for a section = OUTPUT of the immediately prior section,
               which is computed client-side (same logic as before).        */
            COUNT(isl.name)    AS scan_count,

            /* Knitting-specific columns */
            SUM(CASE WHEN op.custom_operation_type = 'KNITTING'
                          AND isl.shift = 'Shift 1'
                     THEN COALESCE(pi.quantity, 1) ELSE 0 END) AS knitting_shift1,
            SUM(CASE WHEN op.custom_operation_type = 'KNITTING'
                          AND isl.shift = 'Shift 2'
                     THEN COALESCE(pi.quantity, 1) ELSE 0 END) AS knitting_shift2,
            SUM(CASE WHEN op.custom_operation_type = 'KNITTING'
                     THEN COALESCE(pi.wastage_qty, 0) ELSE 0 END) AS knitting_wastage,

            SUM(COALESCE(pi.quantity, 1)) AS output_qty

        FROM `tabItem Scan Log` isl

        LEFT JOIN `tabProduction Item` pi
            ON isl.production_item = pi.name

        LEFT JOIN `tabTracking Order Bundle Configuration` tbc
            ON pi.bundle_configuration = tbc.name
            AND tbc.parentfield = 'component_bundle_configurations'

        LEFT JOIN `tabTracking Component` tc
            ON pi.component = tc.name

        LEFT JOIN `tabTracking Order` tor
            ON tc.parent = tor.name

        LEFT JOIN `tabOperation` op
            ON isl.operation = op.name

        LEFT JOIN `tabItem` itm
            ON tor.item = itm.name

        WHERE
            isl.log_status = 'Completed'
            AND DATE(isl.logged_time) BETWEEN %(from_date)s AND %(to_date)s

        GROUP BY
            tbc.sales_order,
            tbc.work_order,
            tor.name,
            pi.size,
            UPPER(TRIM(COALESCE(isl.physical_cell, ''))),
            UPPER(TRIM(COALESCE(op.custom_operation_type, '')))
        """,
        {"from_date": from_date, "to_date": to_date},
        as_dict=1,
    )

    return _pivot_to_rows(raw)


# Section key → canonical bucket name (mirrors SECTION_KEY_MAP in JS)
SECTION_BUCKET = {
    "KNITTING":     "KNITTING",
    "MENDING":      "MENDING",
    "WASHING":      "WASHING",
    "CUTTING":      "CUTTING",
    "LINKING":      "LINKING",
    "SEWING":       "SEWING",
    "EMBROIDERY":   "EMBROIDERY",
    "PRODUCTION":   "PRODUCTION",   # "PRODUCTION OUT" in UI
    "PRESSING":     "PRESSING",
    "FINAL CHECK":  "FINAL CHECK",  # "FINAL CHECKING" in UI
    "PACKING":      "PACKING",
}


def _resolve_bucket(row):
    """Pick the canonical bucket for a raw row."""
    for key in (row.get("physical_cell", ""), row.get("operation_type", "")):
        if key in SECTION_BUCKET:
            return SECTION_BUCKET[key]
    return None


def _pivot_to_rows(raw):
    """
    Group raw SQL rows into one record per (sales_order, work_order,
    tracking_order, size) with a nested `cells` dict.
    """
    groups = {}

    for r in raw:
        bucket = _resolve_bucket(r)
        if not bucket:
            continue

        gkey = (
            r.get("sales_order") or "",
            r.get("work_order")   or "",
            r.get("tracking_order") or "",
            r.get("size") or "",
        )

        if gkey not in groups:
            groups[gkey] = {
                "sales_order":    r.get("sales_order"),
                "work_order":     r.get("work_order"),
                "tracking_order": r.get("tracking_order"),
                "fg_item":        r.get("fg_item"),
                "size":           r.get("size"),
                "brand":          r.get("brand"),
                "planned_qty":    0,
                "knitting_shift1":  0,
                "knitting_shift2":  0,
                "knitting_wastage": 0,
                "cells": {},
            }

        g = groups[gkey]
        out = r.get("output_qty") or 0

        if bucket not in g["cells"]:
            g["cells"][bucket] = {"in": 0, "out": 0}

        g["cells"][bucket]["out"] += out

        # Knitting shift / wastage accumulation
        if bucket == "KNITTING":
            g["knitting_shift1"]  += r.get("knitting_shift1")  or 0
            g["knitting_shift2"]  += r.get("knitting_shift2")  or 0
            g["knitting_wastage"] += r.get("knitting_wastage") or 0

    return list(groups.values())


def _aggregate_output(rows):
    """
    Returns { SECTION_KEY: total_output } summed across all rows.
    Used for MTD / YTD.
    """
    totals = {k: 0 for k in SECTION_BUCKET.values()}

    for row in rows:
        cells = row.get("cells") or {}
        for bucket, vals in cells.items():
            if bucket in totals:
                totals[bucket] += vals.get("out", 0)

        # Knitting output = shift1 + shift2
        knit_out = (row.get("knitting_shift1") or 0) + (row.get("knitting_shift2") or 0)
        totals["KNITTING"] = totals.get("KNITTING", 0)
        # Already counted via cells["KNITTING"]["out"] above; avoid double-count.

    return totals