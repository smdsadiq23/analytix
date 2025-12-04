# Copyright (c) 2025, CognitionX Logic India Private Limited
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from analytix.utils.company import resolve_company, add_company_condition


def execute(filters=None):
    """
    Rework Percentage Report
    - Shows rework instances from 'iridescent_reworktime_view'
    - Filters by date (defect identified date), physical_cell, operation
    - Computes total rework count in summary
    """
    filters = filters or {}
    if not filters.get("from_date") or not filters.get("to_date"):
         frappe.throw("Please select From Date and To Date.")

    from_dt = datetime.combine(frappe.utils.getdate(filters["from_date"]), datetime.min.time())
    to_dt = datetime.combine(frappe.utils.getdate(filters["to_date"]), datetime.max.time())

    #start_dt = frappe.utils.getdate(filters["from_date"])
    #end_dt = frappe.utils.getdate(filters["to_date"]) + timedelta(days=1)

    # ---- Company scoping ----
    company = resolve_company(explicit=filters.get("company"))

	    # ---- Build base conditions for defect logs ----
    defect_conds = [
        "defect.log_type = 'Defect'",
        "defect.log_status = 'Completed'",
        "defect.logged_time >= %(from_dt)s",
        "defect.logged_time <= %(to_dt)s",
    ]
    params = {"from_dt": from_dt, "to_dt": to_dt}

    # Apply company via production_item → Tracking Order
    add_company_condition(
        defect_conds, params, table_alias="tor", company=company,
        join_field="pi.component"  # assuming pi.component links to Tracking Component
    )

    # ---- Filters: physical_cell → workstation, operation → operation ----
    # In Frappe, "Physical Cell" = workstation
    if filters.get("physical_cell"):
        defect_conds.append("defect.workstation = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]

    if filters.get("operation"):
        defect_conds.append("defect.operation = %(operation)s")
        params["operation"] = filters["operation"]

    pc_csv = (filters.get("physical_cell_csv") or "").strip().strip(",")
    op_csv = (filters.get("operation_csv") or "").strip().strip(",")

    if pc_csv:
        defect_conds.append("FIND_IN_SET(defect.workstation, %(pc_csv)s)")
        params["pc_csv"] = pc_csv

    if op_csv:
        defect_conds.append("FIND_IN_SET(defect.operation, %(op_csv)s)")
        params["op_csv"] = op_csv

    defect_where = " AND ".join(defect_conds)

    # ---- Main Query: Defect + First Pass After ----
    rows = frappe.db.sql(
        f"""
        SELECT
            DATE(defect.logged_time) AS defect_date,
            defect.workstation AS physical_cell,
            defect.operation,
            pi.work_order AS wo,
            defect.production_item AS rfid_tag,
            1 AS rework_qty,
            COALESCE(TIMESTAMPDIFF(MINUTE, defect.logged_time, pass.logged_time), 999999) AS leadtime,
            CASE
                WHEN pass.logged_time IS NULL THEN
                    CASE
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, %(now)s) < 500 THEN '<500 Min'
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, %(now)s) < 1000 THEN '<1000 Min'
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, %(now)s) < 1500 THEN '<1500 Min'
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, %(now)s) < 2000 THEN '<2000 Min'
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, %(now)s) < 2500 THEN '<2500 Min'
                        ELSE '>=2500 Min'
                    END
                ELSE
                    CASE
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, pass.logged_time) < 30 THEN '<30 Min'
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, pass.logged_time) < 50 THEN '<50 Min'
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, pass.logged_time) < 120 THEN '<120 Min'
                        WHEN TIMESTAMPDIFF(MINUTE, defect.logged_time, pass.logged_time) < 150 THEN '<150 Min'
                        ELSE '>=150 Min'
                    END
            END AS leadtime_interval

        FROM `tabItem Scan Log` defect
        LEFT JOIN `tabProduction Item` pi ON defect.production_item = pi.name

        -- Find first PASS after defect
        LEFT JOIN (
            SELECT
                isl1.production_item,
                MIN(isl1.logged_time) AS logged_time
            FROM `tabItem Scan Log` isl1
            WHERE
                isl1.log_type = 'Output'
                AND isl1.status = 'Pass'
                AND isl1.log_status = 'Completed'
            GROUP BY isl1.production_item
        ) pass ON (
            defect.production_item = pass.production_item
            AND pass.logged_time > defect.logged_time
        )

        -- Company join
        LEFT JOIN `tabTracking Component` tc ON pi.component = tc.name
        LEFT JOIN `tabTracking Order` tor ON tc.parent = tor.name

        WHERE {defect_where}
        ORDER BY defect.logged_time ASC
        """,
        {**params, "now": frappe.utils.now_datetime()},
        as_dict=True,
    )

    total_rework = len(rows)  # each row = 1 rework instance

    columns = [
        {"label": "Defect Date",            "fieldname": "defect_date",       "fieldtype": "Date",    "width": 100},
        {"label": "Physical Cell",          "fieldname": "physical_cell",     "fieldtype": "Data",    "width": 140},
        {"label": "Operation",              "fieldname": "operation",         "fieldtype": "Data",    "width": 160},
        {"label": "Work Order",             "fieldname": "wo",                "fieldtype": "Data",    "width": 120},
        {"label": "Production Item",        "fieldname": "rfid_tag",          "fieldtype": "Link",    "options": "Production Item", "width": 150},
        {"label": "Rework Qty",             "fieldname": "rework_qty",        "fieldtype": "Int",     "width": 100},
        {"label": "Lead Time (Min)",        "fieldname": "leadtime",          "fieldtype": "Int",     "width": 130},
        {"label": "Time Interval",          "fieldname": "leadtime_interval", "fieldtype": "Data",    "width": 130},
    ]

    summary = [
        {"label": "Total Rework Instances", "value": total_rework, "indicator": "orange"},
    ]


    return columns, rows, None, None, summary