# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from analytix.utils.company import resolve_company, add_company_condition


def execute(filters=None):
    """
    Cell Output vs Plan (Hourly + Daily feeder for viewer)
    - Includes ONLY rows where the Item Scan Log's operation is the cell's 'last operation'
      for the corresponding Tracking Order.
      Mapping table: `tabTracking Order Physical Cell Last Operation` (physical_cell, operation, parent=tracking order)
      Join key to production items: `tabProduction Item`.tracking_order
    - Output = SUM(pi.quantity)
    - Plan   = 0 (placeholder)
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
        "isl.status IN ('Counted', 'Activated', 'Passed')",
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time < %(end_dt)s",
        # last-op constraint (see join below): ensure we only keep rows where isl.operation = lo.operation
        "lo.operation IS NOT NULL",
        "isl.operation = lo.operation",
    ]
    params = {"start_dt": start_dt, "end_dt": end_dt}

    add_company_condition(conds, params, table_alias="tor", company=company)

    # ---- Optional single-value Physical Cell (back-compat) ----
    if filters.get("physical_cell"):
        conds.append("isl.physical_cell = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]

    # ---- Optional CSV from custom pages (kept for reuse) ----
    pc_csv = (filters.get("physical_cell_csv") or "").strip().strip(",")
    if pc_csv:
        conds.append("FIND_IN_SET(isl.physical_cell, %(pc_csv)s)")
        params["pc_csv"] = pc_csv

    where_clause = " AND ".join(conds)

    # ---- Query (hourly aggregation for the selected date) ----
    rows = frappe.db.sql(
        f"""
        SELECT
            DATE(isl.logged_time) AS date,
            HOUR(isl.logged_time) AS hour_num,
            -- start-of-hour label
            CONCAT(LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'), ':00') AS hour_label,
            isl.physical_cell,
            lo.operation AS operation,  -- the 'last operation' per cell for the tracking order
            COALESCE(SUM(COALESCE(pi.quantity, 0)), 0) AS output,
            0 AS plan
        FROM `tabItem Scan Log` isl
        LEFT JOIN `tabProduction Item`  pi ON isl.production_item = pi.name
        LEFT JOIN `tabTracking Component` tc ON pi.component = tc.name
        LEFT JOIN `tabTracking Order`    tor ON tc.`parent` = tor.name
        -- tie to 'last operation per cell' for the tracking order this item belongs to
        LEFT JOIN `tabTracking Order Physical Cell Last Operation` lo
               ON  lo.parent        = pi.tracking_order
               AND lo.physical_cell = isl.physical_cell
        WHERE {where_clause}
        GROUP BY DATE(isl.logged_time), HOUR(isl.logged_time),
                 isl.physical_cell, lo.operation
        ORDER BY hour_num ASC
        """,
        params,
        as_dict=True,
    )

    # ---- Columns / Summary ----
    columns = [
        {"label": "Date",                 "fieldname": "date",          "fieldtype": "Date",  "width": 100},
        {"label": "Hour (HH:00)",         "fieldname": "hour_label",    "fieldtype": "Data",  "width": 120},
        {"label": "Physical Cell",        "fieldname": "physical_cell", "fieldtype": "Data",  "width": 140},
        {"label": "Operation (Last)",     "fieldname": "operation",     "fieldtype": "Link",  "options": "Operation", "width": 160},
        {"label": "Output (Qty)",         "fieldname": "output",        "fieldtype": "Float", "width": 130},
        {"label": "Plan (Qty)",           "fieldname": "plan",          "fieldtype": "Float", "width": 90},
    ]

    total_output = sum((r.get("output") or 0) for r in rows)
    summary = [
        {"label": "Total Output (Qty)", "value": total_output, "indicator": "green" if total_output else "gray"},
        {"label": "Plan (Daily)",       "value": 0,            "indicator": "blue"},
    ]

    return columns, rows, None, None, summary
