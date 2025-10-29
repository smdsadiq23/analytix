# Copyright (c) 2025, CognitionX Logic India Private Limited
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from analytix.utils.company import resolve_company, add_company_condition


def execute(filters=None):
    """
    Output vs Target (Hourly)
    - Output = SUM(pi.quantity) per hour
    - Target = SUM(hourly_target.target) grouped by hour range
    - Returns only columns and rows (no chart)
    Supports:
      - physical_cell_csv: "CellA,CellB,..."
      - operation_csv:     "Op1,Op2,..."
      - Backward compatible with single 'physical_cell' / 'operation'
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
        "isl.status IN ('Counted', 'Activated', 'Pass')",
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time < %(end_dt)s",
    ]
    params = {"start_dt": start_dt, "end_dt": end_dt}

    add_company_condition(conds, params, table_alias="tor", company=company)

    # ---- Filters: single value (back-compat) ----
    if filters.get("physical_cell"):
        conds.append("isl.physical_cell = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]

    if filters.get("operation"):
        conds.append("isl.operation = %(operation)s")
        params["operation"] = filters["operation"]

    # ---- Filters: multi-select CSV ----
    pc_csv = (filters.get("physical_cell_csv") or "").strip().strip(",")
    op_csv = (filters.get("operation_csv") or "").strip().strip(",")

    if pc_csv:
        conds.append("FIND_IN_SET(isl.physical_cell, %(pc_csv)s)")
        params["pc_csv"] = pc_csv

    if op_csv:
        conds.append("FIND_IN_SET(isl.operation, %(op_csv)s)")
        params["op_csv"] = op_csv

    where_clause = " AND ".join(conds)

    # ---- Main query (Output) ----
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
            isl.operation,
            COALESCE(SUM(COALESCE(pi.quantity, 0)), 0) AS output
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

    # ---- Secondary query (Hourly Targets) ----
    target_rows = frappe.db.sql(
        """
        SELECT
            DATE(creation) AS date,
            physical_cell,
            operation,
            workstation,
            from_time,
            to_time,
            SUM(target) AS target
        FROM `tabHourly Target`
        WHERE DATE(creation) = %(date)s
        GROUP BY DATE(creation), physical_cell, operation, workstation, from_time, to_time
        """,
        {"date": day},
        as_dict=True,
    )

    # ---- Transform target rows into lookup dict ----
    # Keyed by (date, hour, physical_cell, operation)
    target_map = {}
    for t in target_rows:
        try:
            # Parse from_time to get hour bucket
            from_hour = t["from_time"].hour
            key = (t["date"], from_hour, t["physical_cell"], t["operation"])
            target_map[key] = target_map.get(key, 0) + (t["target"] or 0)
        except Exception:
            continue

    # ---- Merge targets with main rows ----
    for r in rows:
        key = (r["date"], r["hour_num"], r["physical_cell"], r["operation"])
        r["target"] = target_map.get(key, 0)

    # ---- Columns / Summary ----
    columns = [
        {"label": "Date",                   "fieldname": "date",            "fieldtype": "Date",    "width": 100},
        {"label": "Hour (HH:MM - HH:MM)",   "fieldname": "hour_label",      "fieldtype": "Data",    "width": 160},
        {"label": "Physical Cell",          "fieldname": "physical_cell",   "fieldtype": "Data",    "width": 140},
        {"label": "Operation",              "fieldname": "operation",       "fieldtype": "Link",    "options": "Operation", "width": 160},
        {"label": "Output (Qty)",           "fieldname": "output",          "fieldtype": "Float",   "width": 130},
        {"label": "Target (Qty)",           "fieldname": "target",          "fieldtype": "Float",   "width": 120},
    ]

    total_output = sum((r.get("output") or 0) for r in rows)
    total_target = sum((r.get("target") or 0) for r in rows)

    summary = [
        {"label": "Total Output (Qty)", "value": total_output, "indicator": "green" if total_output else "gray"},
        {"label": "Total Target (Qty)", "value": total_target, "indicator": "blue"},
    ]

    return columns, rows, None, None, summary
