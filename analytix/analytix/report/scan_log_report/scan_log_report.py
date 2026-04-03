# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime


@frappe.whitelist()
def get_dashboard_data(date=None, today=None):
    """
    Returns:
        {
            "daily":      [ ...pivoted rows for the selected date... ],
            "mtd_output": { "KNITTING": N, "MENDING": N, ... },
            "ytd_output": { "KNITTING": N, "MENDING": N, ... },
        }
    """
    selected_date = date or frappe.utils.today()
    anchor_today  = today or frappe.utils.today()

    anchor_dt   = datetime.strptime(anchor_today, "%Y-%m-%d").date()
    month_start = anchor_dt.replace(day=1).strftime("%Y-%m-%d")
    year_start  = anchor_dt.replace(month=1, day=1).strftime("%Y-%m-%d")

    daily_raw = _fetch_raw(selected_date, selected_date)
    mtd_raw   = _fetch_raw(month_start,   anchor_today)
    ytd_raw   = _fetch_raw(year_start,    anchor_today)

    return {
        "daily":      _build_pivoted_rows(daily_raw),
        "mtd_output": _sum_by_section(mtd_raw),
        "ytd_output": _sum_by_section(ytd_raw),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_raw(from_date, to_date):
    """
    Uses the exact same joins as the Scan Log Detail report.
    Returns one row per Item Scan Log entry within the date range.
    """
    return frappe.db.sql(
        """
        SELECT
            isl.name                          AS scan_log,
            isl.physical_cell,
            op.custom_operation_type          AS operation_type,
            pi.quantity                       AS bundle_quantity,

            tbc.sales_order,
            tbc.work_order,
            tor.name                          AS tracking_order,
            tor.item                          AS fg_item,
            pi.size,
            itm.brand,
            wo.qty                            AS work_order_qty

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

        LEFT JOIN `tabWork Order` wo
            ON tbc.work_order = wo.name

        WHERE
            isl.log_status = 'Completed'
            AND DATE(isl.logged_time) BETWEEN %(from_date)s AND %(to_date)s
        """,
        {"from_date": from_date, "to_date": to_date},
        as_dict=1,
    )


# Canonical section keys — must match SECTION_KEY_MAP values in the JS
KNOWN_SECTIONS = {
    "KNITTING", "MENDING", "WASHING", "CUTTING", "LINKING",
    "SEWING", "EMBROIDERY", "PRODUCTION", "PRESSING", "FINAL CHECK", "PACKING",
}


def _resolve_section(row):
    """Try physical_cell first, then operation_type."""
    for field in ("physical_cell", "operation_type"):
        val = (row.get(field) or "").strip().upper()
        if val in KNOWN_SECTIONS:
            return val
    return None


def _build_pivoted_rows(raw):
    """
    Groups raw rows by (sales_order, work_order, tracking_order, size)
    and builds a `cells` dict: { SECTION_KEY: { "in": 0, "out": N } }
    which is exactly what the JS _aggregateTotals() iterates over.
    Knitting output is also written to knitting_shift1 so the existing
    WIP calculation (prev_out = shift1 + shift2) keeps working.
    """
    groups = {}

    for r in raw:
        section = _resolve_section(r)
        if not section:
            continue

        gkey = (
            r.get("sales_order")    or "",
            r.get("work_order")     or "",
            r.get("tracking_order") or "",
            r.get("size")           or "",
        )

        if gkey not in groups:
            groups[gkey] = {
                "sales_order":      r.get("sales_order"),
                "work_order":       r.get("work_order"),
                "tracking_order":   r.get("tracking_order"),
                "fg_item":          r.get("fg_item"),
                "size":             r.get("size"),
                "brand":            r.get("brand"),
                "planned_qty":      r.get("work_order_qty") or 0,
                "knitting_shift1":  0,
                "knitting_shift2":  0,
                "knitting_wastage": 0,
                "cells": {},
            }

        g   = groups[gkey]
        qty = r.get("bundle_quantity") or 1

        if section not in g["cells"]:
            g["cells"][section] = {"in": 0, "out": 0}
        g["cells"][section]["out"] += qty

        # Mirror knitting output into shift1 so the JS WIP formula works
        if section == "KNITTING":
            g["knitting_shift1"] += qty

    return list(groups.values())


def _sum_by_section(raw):
    """{ SECTION_KEY: total_output } — used for MTD / YTD."""
    totals = {s: 0 for s in KNOWN_SECTIONS}
    for r in raw:
        section = _resolve_section(r)
        if section:
            totals[section] += (r.get("bundle_quantity") or 1)
    return totals