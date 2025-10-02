# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from analytix.utils.company import resolve_company, add_company_condition


def execute(filters=None):
    """
    Cell Output vs Plan (Hourly)
    - Returns output ONLY from the LAST operation of each Physical Cell,
      as defined in `tabTracking Order Physical Cell Last Operation`.
    - Plan = 0 (placeholder).
    """
    filters = filters or {}
    if not filters.get("date"):
        frappe.throw("Please select a Date.")

    day = frappe.utils.getdate(filters["date"])
    start_dt = datetime.combine(day, datetime.min.time())
    end_dt = start_dt + timedelta(days=1)

    # ---- Company scoping ----
    company = resolve_company(explicit=filters.get("company"))

    # ---- Base conditions ----
    conds = [
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Activated', 'Pass')",  # ✅ 'Pass', not 'Passed'
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time < %(end_dt)s",
    ]
    params = {"start_dt": start_dt, "end_dt": end_dt}

    add_company_condition(conds, params, table_alias="tor", company=company)

    # ---- Physical Cell filter ----
    if filters.get("physical_cell"):
        conds.append("isl.physical_cell = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]

    pc_csv = (filters.get("physical_cell_csv") or "").strip().strip(",")
    if pc_csv:
        conds.append("FIND_IN_SET(isl.physical_cell, %(pc_csv)s)")
        params["pc_csv"] = pc_csv

    where_clause = " AND ".join(conds)

    # ---- Query: INNER JOIN to ensure ONLY last-operation logs are included ----
    rows = frappe.db.sql(
        f"""
        SELECT
            DATE(isl.logged_time) AS date,
            HOUR(isl.logged_time) AS hour_num,
            CONCAT(LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'), ':00') AS hour_label,
            isl.physical_cell,
            lo.operation AS operation,
            COALESCE(SUM(pi.quantity), 0) AS output,
            0 AS plan
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi 
            ON isl.production_item = pi.name
        INNER JOIN `tabTracking Component` tc 
            ON pi.component = tc.name AND tc.is_main = 1
        INNER JOIN `tabTracking Order` tor 
            ON tc.parent = tor.name
        -- ✅ CRITICAL: INNER JOIN to Last Operation table via tor.name
        INNER JOIN `tabTracking Order Physical Cell Last Operation` lo
            ON lo.parent = tor.name
            AND lo.physical_cell = isl.physical_cell
            AND lo.operation = isl.operation   -- ✅ Enforce match
        WHERE {where_clause}
        GROUP BY DATE(isl.logged_time), HOUR(isl.logged_time),
                 isl.physical_cell, lo.operation
        ORDER BY hour_num ASC
        """,
        params,
        as_dict=True,
    )

    columns = [
        {"label": "Date",                 "fieldname": "date",          "fieldtype": "Date",  "width": 100},
        {"label": "Hour (HH:00)",         "fieldname": "hour_label",    "fieldtype": "Data",  "width": 120},
        {"label": "Physical Cell",        "fieldname": "physical_cell", "fieldtype": "Link",  "options": "Physical Cell", "width": 140},
        {"label": "Operation (Last)",     "fieldname": "operation",     "fieldtype": "Link",  "options": "Operation", "width": 160},
        {"label": "Output (Qty)",         "fieldname": "output",        "fieldtype": "Float", "width": 130},
        {"label": "Plan (Qty)",           "fieldname": "plan",          "fieldtype": "Float", "width": 90},
    ]

    total_output = sum(r.get("output") or 0 for r in rows)
    summary = [
        {"label": "Total Output (Qty)", "value": total_output, "indicator": "green" if total_output else "gray"},
        {"label": "Plan (Daily)",       "value": 0,            "indicator": "blue"},
    ]

    return columns, rows, None, None, summary