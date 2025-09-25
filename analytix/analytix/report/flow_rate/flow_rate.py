# Copyright (c) 2025, CognitionX Logic India Private Limited
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta, time
from analytix.utils.company import resolve_company, add_company_condition


def _hm_from_time_like(val):
    """Accepts datetime.time | datetime.timedelta | 'HH:MM[:SS]' and returns (h, m) or None."""
    if val is None:
        return None
    if isinstance(val, time):
        return int(val.hour), int(val.minute)
    if isinstance(val, timedelta):
        total = int(val.total_seconds())
        total = ((total % 86400) + 86400) % 86400  # normalize into [0, 86400)
        return total // 3600, (total % 3600) // 60
    if isinstance(val, str):
        try:
            dt = datetime.strptime(val, "%H:%M:%S")
        except ValueError:
            dt = datetime.strptime(val, "%H:%M")
        return dt.hour, dt.minute
    return None


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
      - 10-minute buckets for selected date (labels HH:MM)
      - Hourly buckets for selected date (labels HH:00)
      - Output  = SUM(pi.quantity)
      - Target  = 0 (placeholder)
      - Avg     = running average of Output

    Time window:
      - Start at MIN(pc.start_time) over selected cells (or global MIN, or first scan, else 00:00)
      - End at LATER OF MAX(pc.end_time) and last scan time (clamped to the day)
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

    # ---- Filters ----
    if filters.get("physical_cell"):
        conds.append("isl.physical_cell = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]
    if filters.get("operation"):
        conds.append("isl.operation = %(operation)s")
        params["operation"] = filters["operation"]

    pc_csv = (filters.get("physical_cell_csv") or "").strip().strip(",")
    op_csv = (filters.get("operation_csv") or "").strip().strip(",")
    if pc_csv:
        conds.append("FIND_IN_SET(isl.physical_cell, %(pc_csv)s)")
        params["pc_csv"] = pc_csv
    if op_csv:
        conds.append("FIND_IN_SET(isl.operation, %(op_csv)s)")
        params["op_csv"] = op_csv

    where_clause = " AND ".join(conds)

    # ---- Determine chart start & end using Physical Cell bounds + actual data ----
    selected_cells = []
    if pc_csv:
        selected_cells = [x.strip() for x in pc_csv.split(",") if x.strip()]
    elif filters.get("physical_cell"):
        selected_cells = [filters["physical_cell"]]

    # MIN(start_time), MAX(end_time) from tabPhysical Cell
    if selected_cells:
        bounds_row = frappe.db.sql(
            """
            SELECT MIN(pc.start_time) AS min_start,
                MAX(pc.end_time) AS max_end
            FROM `tabPhysical Cell` pc
            WHERE pc.name IN %(cells)s
            AND pc.name <> %(excluded)s
            """,
            {
                "cells": tuple(selected_cells),
                "excluded": "QR/Barcode Cut Bundle Activation",
            },
            as_dict=True,
        )
    else:
        bounds_row = frappe.db.sql(
            """
            SELECT MIN(pc.start_time) AS min_start,
                MAX(pc.end_time) AS max_end
            FROM `tabPhysical Cell` pc
            WHERE pc.name <> %(excluded)s
            """,
            {"excluded": "QR/Barcode Cut Bundle Activation"},
            as_dict=True,
        )

    min_cell_start = (bounds_row[0] or {}).get("min_start") if bounds_row else None
    max_cell_end = (bounds_row[0] or {}).get("max_end") if bounds_row else None

    # First & last actual scan timestamps for the day
    first_last_rows = frappe.db.sql(
        f"""
        SELECT MIN(isl.logged_time) AS first_ts, MAX(isl.logged_time) AS last_ts
        FROM `tabItem Scan Log` isl
        LEFT JOIN `tabProduction Item`  pi ON isl.production_item = pi.name
        LEFT JOIN `tabTracking Component` tc ON pi.component = tc.name
        LEFT JOIN `tabTracking Order`    tor ON tc.`parent` = tor.name
        WHERE {where_clause}
        """,
        params,
        as_dict=True,
    )
    first_ts = (first_last_rows[0] or {}).get("first_ts")
    last_ts = (first_last_rows[0] or {}).get("last_ts")

    # Resolve start H:M (prefer Physical Cell start_time)
    start_h, start_m = 0, 0
    hm = _hm_from_time_like(min_cell_start)
    if hm:
        start_h, start_m = hm
    elif first_ts:
        start_h, start_m = int(first_ts.hour), int(first_ts.minute)

    # Resolve end H:M as later of pc.end_time and last scan
    end_h, end_m = 23, 59  # default if neither is set
    last_h, last_m = (int(last_ts.hour), int(last_ts.minute)) if last_ts else (0, 0)
    hm_end = _hm_from_time_like(max_cell_end)

    if hm_end:
        eh, em = hm_end
        pc_end_min = eh * 60 + em
        data_end_min = last_h * 60 + last_m
        if data_end_min >= pc_end_min:
            end_h, end_m = last_h, last_m
        else:
            end_h, end_m = eh, em
    elif last_ts:
        end_h, end_m = last_h, last_m

    # Clamp to day bounds
    end_h = max(0, min(23, end_h))
    end_m = max(0, min(59, end_m))

    # ---- Query: 10-minute buckets ----
    rows_10 = frappe.db.sql(
        f"""
        SELECT
            DATE(isl.logged_time)             AS date,
            HOUR(isl.logged_time)             AS h,
            FLOOR(MINUTE(isl.logged_time)/10) AS bin10,
            CONCAT(
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'), ':',
                LPAD(CAST(FLOOR(MINUTE(isl.logged_time)/10)*10 AS CHAR), 2, '0')
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

    # Build all 144 bins with start-of-bucket labels (HH:MM)
    slots_10 = [
        {
            "level": "ten_min",
            "bucket_num": h * 6 + b,
            "label": f"{str(h).zfill(2)}:{str(b*10).zfill(2)}",
            "output": 0.0,
            "target": 0.0,
        }
        for h in range(24)
        for b in range(6)
    ]
    for r in rows_10:
        idx = int(r["h"]) * 6 + int(r["bin10"])  # 0..143
        slots_10[idx]["output"] = float(r.get("output") or 0)

    # Trim 10-min series to [start .. end] inclusive
    start_idx_10 = start_h * 6 + (start_m // 10)
    end_idx_10_from_end_time = end_h * 6 + (end_m // 10)
    last_idx_10 = (int(last_ts.hour) * 6 + int(last_ts.minute) // 10) if last_ts else 0
    end_idx_10 = max(end_idx_10_from_end_time, last_idx_10)
    end_idx_10 = max(start_idx_10, min(143, end_idx_10))
    slots_10 = slots_10[start_idx_10 : end_idx_10 + 1]

    # Recompute running average after trimming
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
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'),
                ':00 - ',
                LPAD(CAST(HOUR(isl.logged_time) AS CHAR), 2, '0'),
                ':59'
            ) AS hour_label,
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

    # Build 24 hour bins with start-of-bucket labels (HH:00)
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

    # Trim hourly series to [start_hour .. end_hour] inclusive
    start_idx_hr = start_h
    end_idx_hr_from_end_time = end_h
    last_idx_hr = int(last_ts.hour) if last_ts else 0
    end_idx_hr = max(end_idx_hr_from_end_time, last_idx_hr)
    end_idx_hr = max(start_idx_hr, min(23, end_idx_hr))
    slots_hr = slots_hr[start_idx_hr : end_idx_hr + 1]

    # Recompute hourly running average after trimming
    hr_avg = _running_average([row["output"] for row in slots_hr])
    for i, v in enumerate(hr_avg):
        slots_hr[i]["avg_output"] = v

    # ---- Combine rows for the report grid (viewer splits by 'level') ----
    data = slots_10 + slots_hr

    columns = [
        {"label": "Level",        "fieldname": "level",       "fieldtype": "Data",  "width": 80},
        {"label": "Bucket #",     "fieldname": "bucket_num",  "fieldtype": "Int",   "width": 90},
        {"label": "Time",         "fieldname": "label",       "fieldtype": "Data",  "width": 100},
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
