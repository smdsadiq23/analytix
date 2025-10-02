# Copyright (c) 2025, CognitionX Logic India Private Limited
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from analytix.utils.company import resolve_company, add_company_condition


def execute(filters=None):
    """
    Cell Output vs Plan (Plan = 0 for now)
    - Shows actual output per hour from the LAST operation of each selected Physical Cell.
    - Target is hardcoded to 0 (to be replaced later with real plan data).
    - Filters: physical_cell OR physical_cell_csv (multi-select).
    """
    filters = filters or {}
    if not filters.get("date"):
        frappe.throw("Please select a Date.")

    day = frappe.utils.getdate(filters["date"])
    start_dt = datetime.combine(day, datetime.min.time())
    end_dt = start_dt + timedelta(days=1)

    # ---- Company scoping ----
    company = resolve_company(explicit=filters.get("company"))

    # ---- Build conditions and params ----
    conds = [
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Activated', 'Pass')",
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time < %(end_dt)s",
    ]
    params = {"start_dt": start_dt, "end_dt": end_dt}

    add_company_condition(conds, params, table_alias="tor", company=company)

    # ---- Physical Cell filter (CSV or single) ----
    pc_csv = (filters.get("physical_cell_csv") or "").strip().strip(",")
    if filters.get("physical_cell") and not pc_csv:
        pc_csv = filters["physical_cell"]

    if not pc_csv:
        frappe.throw("Please select at least one Physical Cell.")

    conds.append("FIND_IN_SET(isl.physical_cell, %(pc_csv)s)")
    params["pc_csv"] = pc_csv

    where_clause = " AND ".join(conds)

    # ---- Main Query: Only last-operation output per Physical Cell ----
    rows = frappe.db.sql(
        f"""
        SELECT
            DATE(isl.logged_time) AS date,
            HOUR(isl.logged_time) AS hour_num,
            CONCAT(
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'),
                ':00 - ',
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'),
                ':59'
            ) AS hour_label,
            isl.physical_cell,
            COALESCE(SUM(pi.quantity), 0) AS output,
            0 AS target  -- Placeholder; will be replaced with real plan later
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi 
            ON isl.production_item = pi.name
        INNER JOIN `tabTracking Component` tc 
            ON pi.component = tc.name AND tc.is_main = 1
        INNER JOIN `tabTracking Order` tor 
            ON tc.parent = tor.name
        INNER JOIN `tabTracking Order Physical Cell Last Operation` topclo
            ON topclo.parent = tor.name
            AND topclo.physical_cell = isl.physical_cell
            AND topclo.operation = isl.operation
        WHERE {where_clause}
        GROUP BY DATE(isl.logged_time), HOUR(isl.logged_time), isl.physical_cell
        ORDER BY isl.physical_cell, hour_num
        """,
        params,
        as_dict=True,
    )

    # ---- Columns ----
    columns = [
        {"label": "Date",                   "fieldname": "date",            "fieldtype": "Date",    "width": 100},
        {"label": "Hour (HH:MM - HH:MM)",   "fieldname": "hour_label",      "fieldtype": "Data",    "width": 160},
        {"label": "Physical Cell",          "fieldname": "physical_cell",   "fieldtype": "Link",    "options": "Physical Cell", "width": 160},
        {"label": "Output (Qty)",           "fieldname": "output",          "fieldtype": "Float",   "width": 130},
        {"label": "Plan (Qty)",             "fieldname": "target",          "fieldtype": "Float",   "width": 130},
    ]

    # ---- Summary ----
    total_output = sum(r.get("output") or 0 for r in rows)
    summary = [
        {"label": "Total Output (Qty)", "value": total_output, "indicator": "green" if total_output else "gray"},
        {"label": "Total Plan (Qty)",   "value": 0,            "indicator": "orange"},
    ]

    return columns, rows, None, None, summary