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

    # ---- Base conditions ----
    # We'll filter on dfct_idtfyd_time (when defect was logged)
    conds = [
        "r.dfct_idtfyd_time >= %(from_dt)s",
        "r.dfct_idtfyd_time < %(to_dt)s",
    ]
    params = {"from_dt": from_dt, "to_dt": to_dt}

    # Company filter? Your view doesn't have company, but WO might link to company.
    # Since original report uses `tor` (Tracking Order) for company, but this view uses WO.
    # If `iridescent_wostatus_view` has company, we can join or filter.
    # For now, skip company unless specified in view. But keep placeholder.
    # If needed, you can add: `r.factory_name = %(company)s` if factory_name = company

    # ---- Filters: single value (back-compat) ----
    if filters.get("physical_cell"):
        conds.append("r.`cell` = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]

    if filters.get("operation"):
        conds.append("r.`process` = %(operation)s")
        params["operation"] = filters["operation"]

    # ---- Multi-select CSV (preferred) ----
    pc_csv = (filters.get("physical_cell_csv") or "").strip().strip(",")
    op_csv = (filters.get("operation_csv") or "").strip().strip(",")

    if pc_csv:
        conds.append("FIND_IN_SET(r.`cell`, %(pc_csv)s)")
        params["pc_csv"] = pc_csv

    if op_csv:
        conds.append("FIND_IN_SET(r.`process`, %(op_csv)s)")
        params["op_csv"] = op_csv

    where_clause = " AND ".join(conds)

    # ---- Query the view ----
    rows = frappe.db.sql(
        f"""
        SELECT
            DATE(r.dfct_idtfyd_time) AS defect_date,
            r.`physical line` AS physical_cell,
            r.`process` AS operation,
            r.wo,
            r.`rfid tag` AS rfid_tag,
            r.`bc-sw-qty` AS rework_qty,
            r.leadtime,
            r.`interval` AS leadtime_interval,
            r.sort_order
        FROM `iridescent_reworktime_view` r
        WHERE {where_clause}
        ORDER BY r.sort_order ASC, r.dfct_idtfyd_time ASC
        """,
        params,
        as_dict=True,
    )

    # ---- Columns ----
    columns = [
        {"label": "Defect Date",            "fieldname": "defect_date",       "fieldtype": "Date",    "width": 100},
        {"label": "Physical Cell",          "fieldname": "physical_cell",     "fieldtype": "Data",    "width": 140},
        {"label": "Operation",              "fieldname": "operation",         "fieldtype": "Data",    "width": 160},
        {"label": "Work Order",             "fieldname": "wo",                "fieldtype": "Data",    "width": 120},
        {"label": "RFID Tag",               "fieldname": "rfid_tag",          "fieldtype": "Data",    "width": 150},
        {"label": "Rework Qty",             "fieldname": "rework_qty",        "fieldtype": "Int",     "width": 100},
        {"label": "Lead Time (Min)",        "fieldname": "leadtime",          "fieldtype": "Float",   "width": 130},
        {"label": "Time Interval",          "fieldname": "leadtime_interval", "fieldtype": "Data",    "width": 130},
    ]

    total_rework = sum((r.get("rework_qty") or 0) for r in rows)

    # Optional: If you later want %, you’d need total output.
    # For now, just show total rework count.
    summary = [
        {"label": "Total Rework Qty", "value": total_rework, "indicator": "orange" if total_rework else "gray"},
    ]

    return columns, rows, None, None, summary