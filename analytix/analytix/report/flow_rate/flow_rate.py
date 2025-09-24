# Copyright (c) 2025, CognitionX Logic India Private Limited
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from analytix.utils.company import resolve_company, add_company_condition


def _running_average(values: list[float]) -> list[float]:
    """Return running/rolling average from the start of the series."""
    out: list[float] = []
    total = 0.0
    for i, v in enumerate(values, 1):
        total += float(v or 0)
        out.append(total / i)
    return out


def execute(filters: dict | None = None):
    """
    Flow Rate
      - Chart A: 10‑minute buckets for the selected *date* (00:00–00:09 … 23:50–23:59)
      - Chart B: Hourly buckets for the selected *date* (00:00–00:59 … 23:00–23:59)
      - Output  = SUM(pi.quantity)
      - Target  = 0 (placeholder)
      - Avg line = running average of Output per bucket

    Filters accepted (viewer compatible):
      - date (required)
      - physical_cell / operation (single value, back‑compat)
      - physical_cell_csv / operation_csv (CSV from MultiSelect)
    Returns: columns, data_rows, None, None, summary
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
    conds: list[str] = [
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Activated', 'Passed')",
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time < %(end_dt)s",
    ]
    params: dict = {"start_dt": start_dt, "end_dt": end_dt}

    add_company_condition(conds, params, table_alias="tor", company=company)

    # ---- Single-value filters (back‑compat) ----
    if filters.get("physical_cell"):
        conds.append("isl.physical_cell = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]

    if filters.get("operation"):
        conds.append("isl.operation = %(operation)s")
        params["operation"] = filters["operation"]

    # ---- CSV multi‑select (from viewer) ----
    pc_csv = (filters.get("physical_cell_csv") or "").strip().strip(",")
    op_csv = (filters.get("operation_csv") or "").strip().strip(",")

    if pc_csv:
        conds.append("FIND_IN_SET(isl.physical_cell, %(pc_csv)s)")
        params["pc_csv"] = pc_csv

    if op_csv:
        conds.append("FIND_IN_SET(isl.operation, %(op_csv)s)")
        params["op_csv"] = op_csv

    where_clause = " AND ".join(conds)

    # ---- Query: 10‑minute buckets ----
    rows_10 = frappe.db.sql(
        f"""
        SELECT
            DATE(isl.logged_time)             AS date,
            HOUR(isl.logged_time)             AS h,
            FLOOR(MINUTE(isl.logged_time)/10) AS bin10,
            CONCAT(
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'), ':',
                LPAD(CAST(FLOOR(MINUTE(isl.logged_time)/10)*10 AS CHAR), 2, '0'),
                ' - ',
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'), ':',
                LPAD(CAST(LEAST(FLOOR(MINUTE(isl.logged_time)/10)*10 + 9, 59) AS CHAR), 2, '0')
            ) AS label,
            COALESCE(SUM(COALESCE(pi.quantity, 0)), 0) AS output
        FROM `tabItem Scan Log` isl
        LEFT JOIN `tabProduction Item`  pi ON isl.production_item = pi.name
        LEFT JOIN `tabTracking Component` tc ON pi.component = tc.name
        LEFT JOIN `tabTracking Order`    tor ON tc.`parent` = tor.name
        WHERE {where_clause}
        GROUP BY DATE(isl.logged_time), HOUR(isl.logged_time), FLOOR(MINUTE(isl.logged_time)/10)
        ORDER BY h ASC, bin10 ASC
        """,
        params,
        as_dict=True,
    )

    # Pre‑build 144 slots for 24h * 6 bins per hour
    slots_10 = [
        {
            "level": "ten_min",
            "bucket_num": h * 6 + b,
            "label": f"{str(h).zfill(2)}:{str(b*10).zfill(2)} - {str(h).zfill(2)}:{str(min(b*10+9,59)).zfill(2)}",
            "output": 0.0,
            "target": 0.0,
        }
        for h in range(24)
        for b in range(6)
    ]
    for r in rows_10:
        idx = int(r["h"]) * 6 + int(r["bin10"])  # 0..143
        slots_10[idx]["output"] = float(r.get("output") or 0)

    # running average for 10‑min series
    ten_avg = _running_average([row["output"] for row in slots_10])
    for i, v in enumerate(ten_avg):
        slots_10[i]["avg_output"] = v

    # ---- Query: hourly buckets ----
    rows_hr = frappe.db.sql(
        f"""
        SELECT
            DATE(isl.logged_time) AS date,
            HOUR(isl.logged_time) AS h,
            CONCAT(
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'), ':00 - ',
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'), ':59'
            ) AS label,
            COALESCE(SUM(COALESCE(pi.quantity, 0)), 0) AS output
        FROM `tabItem Scan Log` isl
        LEFT JOIN `tabProduction Item`  pi ON isl.production_item = pi.name
        LEFT JOIN `tabTracking Component` tc ON pi.component = tc.name
        LEFT JOIN `tabTracking Order`    tor ON tc.`parent` = tor.name
        WHERE {where_clause}
        GROUP BY DATE(isl.logged_time), HOUR(isl.logged_time)
        ORDER BY h ASC
        """,
        params,
        as_dict=True,
    )

    # Pre‑build 24 slots
    slots_hr = [
        {
            "level": "hour",
            "bucket_num": h,
            "label": f"{str(h).zfill(2)}:00 - {str(h).zfill(2)}:59",
            "output": 0.0,
            "target": 0.0,
        }
        for h in range(24)
    ]
    for r in rows_hr:
        idx = int(r["h"])  # 0..23
        slots_hr[idx]["output"] = float(r.get("output") or 0)

    hr_avg = _running_average([row["output"] for row in slots_hr])
    for i, v in enumerate(hr_avg):
        slots_hr[i]["avg_output"] = v

    # ---- Combine rows for the report grid (viewer will split by level) ----
    data = slots_10 + slots_hr

    columns = [
        {"label": "Level",        "fieldname": "level",       "fieldtype": "Data",  "width": 80},
        {"label": "Bucket #",     "fieldname": "bucket_num",  "fieldtype": "Int",   "width": 90},
        {"label": "Time Window",  "fieldname": "label",       "fieldtype": "Data",  "width": 150},
        {"label": "Output (Qty)", "fieldname": "output",      "fieldtype": "Float", "width": 120},
        {"label": "Target (Qty)", "fieldname": "target",      "fieldtype": "Float", "width": 120},
        {"label": "Avg Output",   "fieldname": "avg_output",  "fieldtype": "Float", "width": 120},
    ]

    total_output = sum((r.get("output") or 0) for r in slots_hr)
    summary = [
        {"label": "Total Output (Qty)", "value": total_output, "indicator": "green" if total_output else "gray"},
        {"label": "Target (Daily)",     "value": 0,            "indicator": "blue"},
    ]

    return columns, data, None, None, summary
