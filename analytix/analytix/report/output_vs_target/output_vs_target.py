# Copyright (c) 2025, CognitionX Logic India Private Limited
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from analytix.utils.company import resolve_company, add_company_condition


def execute(filters=None):
    """
    Output vs Target (Hourly)
    - Output = SUM(pi.quantity) per hour (not COUNT of scans)
    - Target = 0 (placeholder)
    - Returns only columns and rows (no chart)

    Filters expected:
      - date (required)
      - physical_cell (optional)
      - operation (optional)
      - company (optional; respected for SysMgrs or when helper returns it)
    """
    filters = filters or {}

    if not filters.get("date"):
        frappe.throw("Please select a Date.")

    day = frappe.utils.getdate(filters["date"])
    start_dt = datetime.combine(day, datetime.min.time())
    end_dt = start_dt + timedelta(days=1)

    # ---- Company scoping (one-liner via helper) ----
    # resolve_company() order:
    #   explicit -> user default -> Global Defaults -> (SysMgr unrestricted) -> else error
    company = resolve_company(explicit=filters.get("company"))

    # WHERE clause
    conds = [
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Activated', 'Pass')",
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time < %(end_dt)s",
    ]
    params = {"start_dt": start_dt, "end_dt": end_dt}

    # add `tor.company = %(company)s` if company is truthy
    add_company_condition(conds, params, table_alias="tor", company=company)

    if filters.get("physical_cell"):
        conds.append("isl.physical_cell = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]

    if filters.get("operation"):
        conds.append("isl.operation = %(operation)s")
        params["operation"] = filters["operation"]

    where_clause = " AND ".join(conds)

    rows = frappe.db.sql(
        f"""
        SELECT
            DATE(isl.logged_time) AS date,
            HOUR(isl.logged_time) AS hour_num,
            LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0') AS hour_label,
            isl.physical_cell,
            isl.operation,
            COALESCE(SUM(COALESCE(pi.quantity, 0)), 0) AS output,
            0 AS target
        FROM `tabItem Scan Log` isl
        LEFT JOIN `tabProduction Item`  pi ON isl.production_item = pi.name
        LEFT JOIN `tabTracking Component` tc ON pi.component = tc.name
        LEFT JOIN `tabTracking Order`    tor ON tc.`parent` = tor.name
        WHERE {where_clause}
        GROUP BY DATE(isl.logged_time), HOUR(isl.logged_time),
                 isl.physical_cell, isl.operation
        ORDER BY hour_num ASC
        """,
        params,
        as_dict=True,
    )

    columns = [
        {"label": "Date",            "fieldname": "date",         "fieldtype": "Date",  "width": 100},
        {"label": "Hour",            "fieldname": "hour_label",   "fieldtype": "Data",  "width": 80},
        {"label": "Physical Cell",   "fieldname": "physical_cell","fieldtype": "Data",  "width": 140},
        {"label": "Operation",       "fieldname": "operation",    "fieldtype": "Link",  "options": "Operation", "width": 160},
        {"label": "Output (Qty)",    "fieldname": "output",       "fieldtype": "Float", "width": 130},
        {"label": "Target",          "fieldname": "target",       "fieldtype": "Float", "width": 90},
    ]

    total_output = sum((r.get("output") or 0) for r in rows)
    summary = [
        {"label": "Total Output (Qty)", "value": total_output, "indicator": "green" if total_output else "gray"},
        {"label": "Target (Daily)",     "value": 0,            "indicator": "blue"},
    ]

    # Return WITHOUT chart/message
    return columns, rows, None, None, summary
