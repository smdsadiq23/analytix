# Copyright (c) 2025,
# CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from frappe.utils import nowdate, getdate

# Count only "good" progress scans for TPT timing.
ALLOWED_STATUSES = ("Counted", "Activated", "Pass")


def execute(filters=None):
    """
    Unit Throughput Time (Python aggregation)

    Returns message payload with two datasets:
      - {"name": "by_cell", "data": [
            { physical_cell, first_ts, last_op, last_ts, tpt_seconds, tpt_hhmm }
        ]}
      - {"name": "overall", "data": [
            { tracking_order, first_op, first_ts, last_op, last_ts, tpt_seconds, tpt_hhmm }
        ]}

    Filters (all optional):
      - date (YYYY-MM-DD) OR date_range = [from_date, to_date]   (date_range has precedence)
      - sales_order
      - work_order
      - style  (matches Item.custom_style_master via WO.production_item or SOI.item_code)
    """
    filters = filters or {}

    # --------- Resolve date window ---------
    start_dt, end_dt = _resolve_datetime_window(filters)

    # --------- Optional entity filters ---------
    so_filter = (filters.get("sales_order") or "").strip()
    wo_filter = (filters.get("work_order") or "").strip()
    style_filter = (filters.get("style") or "").strip()

    # --------- Load data with simple queries ---------
    scan_rows = _load_scans(
        start_dt, end_dt,
        sales_order=so_filter,
        work_order=wo_filter,
        style=style_filter,
    )

    if not scan_rows:
        return [], [], None, None, [
            {"name": "by_cell", "data": []},
            {"name": "overall", "data": []},
        ]

    # Build mappings from Cut Kit Plan → per-cell first/last ops
    cell_first_last_map, tor_first_last_map = _build_first_last_op_mappings()

    # --------- Build indices in Python ---------
    idx = _index_scans(scan_rows)

    # --------- 1) TPT by PHYSICAL CELL (only units that reached cell's last op) ---------
    by_cell = _compute_tpt_by_cell(idx, cell_first_last_map)

    # --------- 2) TPT for WHOLE PROCESS MAP (only units that reached any "last op") ----
    overall = _compute_tpt_overall(idx, tor_first_last_map)

    return [], [], None, None, [
        {"name": "by_cell", "data": by_cell},
        {"name": "overall", "data": overall},
    ]


# ======================================================================
#                             LOADERS
# ======================================================================

def _load_scans(start_dt, end_dt, sales_order, work_order, style):
    """
    Fetch scan facts with strong, optional filters (date + SO/WO/style).
    """
    conds = [
        "isl.log_status = 'Completed'",
        f"isl.status IN {sql_tuple(ALLOWED_STATUSES)}",
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time <  %(end_dt)s",
    ]
    params = {"start_dt": start_dt, "end_dt": end_dt}

    # SO filter via EXISTS against TBC
    if sales_order:
        conds.append("""
            EXISTS (
              SELECT 1
              FROM `tabTracking Order Bundle Configuration` tbc_so
              WHERE tbc_so.parent = tor.name
                AND tbc_so.name = pi.bundle_configuration
                AND tbc_so.parentfield = 'component_bundle_configurations'
                # AND tbc_so.activation_status = 'Completed'
                AND tbc_so.sales_order = %(sales_order)s
            )
        """)
        params["sales_order"] = sales_order

    # WO filter via EXISTS against TBC
    if work_order:
        conds.append("""
            EXISTS (
              SELECT 1
              FROM `tabTracking Order Bundle Configuration` tbc_wo
              WHERE tbc_wo.parent = tor.name
                AND tbc_wo.name = pi.bundle_configuration
                AND tbc_wo.parentfield = 'component_bundle_configurations'
                # AND tbc_wo.activation_status = 'Completed'
                AND tbc_wo.work_order = %(work_order)s
            )
        """)
        params["work_order"] = work_order

    # Style filter: Item.custom_style_master through WO and SOI (no PI fallback)
    if style:
        conds.append("""
        (
          /* WO.production_item -> Item.custom_style_master */
          EXISTS (
            SELECT 1
            FROM `tabTracking Order Bundle Configuration` tbc_st
            JOIN `tabWork Order` wo_st ON wo_st.name = tbc_st.work_order
            JOIN `tabItem` it_wo ON it_wo.name = wo_st.production_item
            WHERE tbc_st.parent = tor.name
              AND tbc_st.name   = pi.bundle_configuration
              AND tbc_st.parentfield = 'component_bundle_configurations'
            #   AND tbc_st.activation_status = 'Completed'
              AND it_wo.custom_style_master = %(style)s
          )
          OR
          /* Sales Order Items -> Item.custom_style_master */
          EXISTS (
            SELECT 1
            FROM `tabTracking Order Bundle Configuration` tbc_st2
            JOIN `tabSales Order Item` soi2 ON soi2.parent = tbc_st2.sales_order
            JOIN `tabItem` it_so ON it_so.name = soi2.item_code
            WHERE tbc_st2.parent = tor.name
              AND tbc_st2.name   = pi.bundle_configuration
              AND tbc_st2.parentfield = 'component_bundle_configurations'
            #   AND tbc_st2.activation_status = 'Completed'
              AND it_so.custom_style_master = %(style)s
          )
        )
        """)
        params["style"] = style

    where_sql = " AND ".join(conds)

    rows = frappe.db.sql(
        f"""
        SELECT
          isl.physical_cell,
          isl.operation,
          isl.logged_time,
          tc.parent AS tracking_order,
          pi.name   AS pi_name
        FROM `tabItem Scan Log` isl
        LEFT JOIN `tabProduction Item`  pi
               ON pi.name = isl.production_item
        LEFT JOIN `tabTracking Component` tc
               ON tc.name = pi.component AND tc.is_main = 1
        LEFT JOIN `tabTracking Order` tor
               ON tor.name = tc.parent
        WHERE {where_sql}
        """,
        params,
        as_dict=True,
    )
    return rows


def _build_first_last_op_mappings():
    """
    Build two mappings from Cut Kit Plan data:
    1. (tracking_order, physical_cell) → {first, last}
    2. tracking_order → {first, last}
    """
    ckp_data = frappe.db.sql("""
        SELECT
            tor.name AS tracking_order,
            cko.physical_cell,
            cko.first_operation,
            cko.last_operation
        FROM `tabCut Kit Plan` ckp
        INNER JOIN `tabTracking Order` tor 
            ON tor.reference_order_number = ckp.cut_bundle_order
        INNER JOIN `tabPhysical Cell First and Last Operation` cko 
            ON cko.parent = ckp.name
        WHERE ckp.docstatus = 1
    """, as_dict=True)

    cell_map = {}
    tor_map = {}

    for row in ckp_data:
        tor = row.tracking_order
        cell = row.physical_cell
        cell_map[(tor, cell)] = {
            "first": row.first_operation,
            "last": row.last_operation
        }
        # For overall TPT, pick any cell's ops (they should be consistent per TOR)
        if tor not in tor_map:
            tor_map[tor] = {
                "first": row.first_operation,
                "last": row.last_operation
            }

    return cell_map, tor_map


# ======================================================================
#                             INDEX BUILDERS
# ======================================================================

def _index_scans(scan_rows):
    from collections import defaultdict

    scans_by_cell = defaultdict(list)
    scans_by_tor = defaultdict(list)
    scans_by_tor_op = defaultdict(list)
    scans_by_cell_tor_op = defaultdict(list)
    scans_by_cell_tor_op_pi = defaultdict(list)

    for r in scan_rows:
        cell = r["physical_cell"]
        op = r["operation"]
        tor = r["tracking_order"]
        ts = r["logged_time"]
        pi = r["pi_name"]

        if not (cell and op and tor and ts and pi):
            continue

        scans_by_cell[cell].append(r)
        scans_by_tor[tor].append(r)
        scans_by_tor_op[(tor, op)].append(r)
        scans_by_cell_tor_op[(cell, tor, op)].append(r)
        scans_by_cell_tor_op_pi[(cell, tor, op, pi)].append(r)

    # Sort by timestamp
    for d in (scans_by_cell, scans_by_tor, scans_by_tor_op, scans_by_cell_tor_op, scans_by_cell_tor_op_pi):
        for k in d:
            d[k].sort(key=lambda x: x["logged_time"] or datetime.min)

    return dict(
        scans_by_cell=scans_by_cell,
        scans_by_tor=scans_by_tor,
        scans_by_tor_op=scans_by_tor_op,
        scans_by_cell_tor_op=scans_by_cell_tor_op,
        scans_by_cell_tor_op_pi=scans_by_cell_tor_op_pi,
    )


# ======================================================================
#                         PYTHON COMPUTATIONS
# ======================================================================

def _compute_tpt_by_cell(idx, cell_first_last_map):
    result = []

    scans_by_cell = idx["scans_by_cell"]
    scans_by_cell_tor_op_pi = idx["scans_by_cell_tor_op_pi"]

    for cell, rows in scans_by_cell.items():
        if not rows:
            continue

        tors = {r["tracking_order"] for r in rows if r.get("tracking_order")}
        pis_that_reached = set()
        last_ts_candidates = []
        first_ts_candidates = []

        for tor in tors:
            key = (tor, cell)
            if key not in cell_first_last_map:
                continue

            first_op = cell_first_last_map[key]["first"]
            last_op = cell_first_last_map[key]["last"]

            pis_in_tor = {r["pi_name"] for r in rows if r["tracking_order"] == tor}

            # Find PIs that reached LAST operation
            for pi in pis_in_tor:
                last_logs = scans_by_cell_tor_op_pi.get((cell, tor, last_op, pi), [])
                if last_logs:
                    pis_that_reached.add(pi)
                    last_ts_candidates.append(last_logs[-1]["logged_time"])

            # Find FIRST operation timestamps for those PIs
            for pi in pis_in_tor:
                if pi in pis_that_reached:
                    first_logs = scans_by_cell_tor_op_pi.get((cell, tor, first_op, pi), [])
                    if first_logs:
                        first_ts_candidates.append(first_logs[0]["logged_time"])

        if not pis_that_reached or not first_ts_candidates or not last_ts_candidates:
            continue

        first_ts = min(first_ts_candidates)
        last_ts = max(last_ts_candidates)
        tpt_seconds = (last_ts - first_ts).total_seconds()

        # Use last_op from mapping
        last_op_selected = cell_first_last_map[(tor, cell)]["last"]

        result.append({
            "physical_cell": cell,
            "first_ts": first_ts,
            "last_op": last_op_selected,
            "last_ts": last_ts,
            "tpt_seconds": tpt_seconds,
            "tpt_hhmm": _fmt_hhmmss(tpt_seconds),
        })

    result.sort(key=lambda r: (r["physical_cell"] or ""))
    return result


def _compute_tpt_overall(idx, tor_first_last_map):
    result = []

    scans_by_tor = idx["scans_by_tor"]
    scans_by_tor_op = idx["scans_by_tor_op"]

    for tor, tor_scans in scans_by_tor.items():
        if not tor_scans or tor not in tor_first_last_map:
            continue

        first_op = tor_first_last_map[tor]["first"]
        last_op = tor_first_last_map[tor]["last"]

        pis_in_tor = {r["pi_name"] for r in tor_scans}

        # Find PIs that reached LAST operation
        pis_that_reached = set()
        for r in scans_by_tor_op.get((tor, last_op), []):
            if r["pi_name"] in pis_in_tor:
                pis_that_reached.add(r["pi_name"])

        if not pis_that_reached:
            continue

        # First timestamps (only for PIs that reached last op)
        first_ts_candidates = [
            r["logged_time"]
            for r in scans_by_tor_op.get((tor, first_op), [])
            if r["pi_name"] in pis_that_reached
        ]

        # Last timestamps
        last_ts_candidates = [
            r["logged_time"]
            for r in scans_by_tor_op.get((tor, last_op), [])
            if r["pi_name"] in pis_that_reached
        ]

        if not first_ts_candidates or not last_ts_candidates:
            continue

        first_ts = min(first_ts_candidates)
        last_ts = max(last_ts_candidates)
        tpt_seconds = (last_ts - first_ts).total_seconds()

        result.append({
            "tracking_order": tor,
            "first_op": first_op,
            "first_ts": first_ts,
            "last_op": last_op,
            "last_ts": last_ts,
            "tpt_seconds": tpt_seconds,
            "tpt_hhmm": _fmt_hhmmss(tpt_seconds),
        })

    result.sort(key=lambda r: (r["tracking_order"] or ""))
    return result


# ======================================================================
#                             UTILITIES
# ======================================================================

def _resolve_datetime_window(filters):
    if filters.get("date_range") and isinstance(filters["date_range"], (list, tuple)) and len(filters["date_range"]) == 2:
        d0 = getdate(filters["date_range"][0])
        d1 = getdate(filters["date_range"][1])
        if d0 > d1:
            d0, d1 = d1, d0
        start_dt = datetime.combine(d0, datetime.min.time())
        end_dt = datetime.combine(d1, datetime.min.time()) + timedelta(days=1)
        return start_dt, end_dt

    day = getdate(filters.get("date") or nowdate())
    start_dt = datetime.combine(day, datetime.min.time())
    end_dt = start_dt + timedelta(days=1)
    return start_dt, end_dt


def sql_tuple(py_tuple):
    return "(" + ",".join([frappe.db.escape(s) for s in py_tuple]) + ")"


def _fmt_hhmmss(seconds):
    if seconds is None or seconds < 0:
        return ""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"