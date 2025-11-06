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
      - physical_cell_csv (CSV list)
      - operation_csv     (CSV list)
      - sales_order
      - work_order
      - style  (matches WO.production_item OR any SOI.item_code under the linked SO, with fallback to PI.item_code)
    """
    filters = filters or {}

    # --------- Resolve date window ---------
    start_dt, end_dt = _resolve_datetime_window(filters)

    # --------- CSV filters -> sets ---------
    pc_filter = _csv_to_set(filters.get("physical_cell_csv"))
    op_filter = _csv_to_set(filters.get("operation_csv"))

    # --------- Optional entity filters ---------
    so_filter = (filters.get("sales_order") or "").strip()
    wo_filter = (filters.get("work_order") or "").strip()
    style_filter = (filters.get("style") or "").strip()

    # --------- Load data with simple queries ---------
    scan_rows = _load_scans(
        start_dt, end_dt,
        pc_filter=pc_filter,
        op_filter=op_filter,
        sales_order=so_filter,
        work_order=wo_filter,
        style=style_filter,
    )

    if not scan_rows:
        return [], [], None, None, [
            {"name": "by_cell", "data": []},
            {"name": "overall", "data": []},
        ]

    # 2) Last operation per (tracking_order, physical_cell)
    topclo_rows = _load_last_ops_per_cell()

    # 3) Operation graph (operation -> next_operation) per tracking_order
    opmap_rows = _load_operation_map()

    # --------- Build indices in Python ---------
    idx = _index_scans(scan_rows)

    # mapping (tracking_order, physical_cell) -> last_operation
    last_op_map = {(r["tracking_order"], r["physical_cell"]): r["last_operation"]
                   for r in topclo_rows}

    # operation graph per TOR
    graph_by_tor = _graph_by_tracking_order(opmap_rows)

    # --------- 1) TPT by PHYSICAL CELL (only units that reached cell's last op) ---------
    by_cell = _compute_tpt_by_cell(idx, last_op_map)

    # --------- 2) TPT for WHOLE PROCESS MAP (only units that reached any "last op") ----
    overall = _compute_tpt_overall(idx, graph_by_tor)

    return [], [], None, None, [
        {"name": "by_cell", "data": by_cell},
        {"name": "overall", "data": overall},
    ]


# ======================================================================
#                             LOADERS
# ======================================================================

def _load_scans(start_dt, end_dt, pc_filter, op_filter, sales_order, work_order, style):
    """
    Fetch scan facts with strong, optional filters. We keep all joins LEFT so rows
    that don't have SO/WO links still pass, but we apply SO/WO/style via EXISTS
    subqueries (so null LEFT-joins won't neuter the filter).
    """
    conds = [
        "isl.log_status = 'Completed'",
        f"isl.status IN {sql_tuple(ALLOWED_STATUSES)}",
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time <  %(end_dt)s",
    ]
    params = {"start_dt": start_dt, "end_dt": end_dt}

    # Physical Cell / Operation filters
    if pc_filter:
        conds.append("FIND_IN_SET(isl.physical_cell, %(pc_csv)s)")
        params["pc_csv"] = ",".join(sorted(pc_filter))

    if op_filter:
        conds.append("FIND_IN_SET(isl.operation, %(op_csv)s)")
        params["op_csv"] = ",".join(sorted(op_filter))

    # SO filter via EXISTS against TBC
    if sales_order:
        conds.append("""
            EXISTS (
              SELECT 1
              FROM `tabTracking Order Bundle Configuration` tbc_so
              WHERE tbc_so.parent = tor.name
                AND tbc_so.name = pi.bundle_configuration
                AND tbc_so.parentfield = 'component_bundle_configurations'
                AND tbc_so.activation_status = 'Completed'
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
                AND tbc_wo.activation_status = 'Completed'
                AND tbc_wo.work_order = %(work_order)s
            )
        """)
        params["work_order"] = work_order

    # Style filter: matches WO.production_item OR any SOI.item_code under that SO OR fallback to PI.item_code
    if style:
        conds.append("""
        (
          EXISTS (
            SELECT 1
            FROM `tabTracking Order Bundle Configuration` tbc_st
            JOIN `tabWork Order` wo_st ON wo_st.name = tbc_st.work_order
            WHERE tbc_st.parent = tor.name
              AND tbc_st.name   = pi.bundle_configuration
              AND tbc_st.parentfield = 'component_bundle_configurations'
              AND tbc_st.activation_status = 'Completed'
              AND wo_st.production_item = %(style)s
          )
          OR EXISTS (
            SELECT 1 FROM `tabTracking Order Bundle Configuration` tbc_st2
            JOIN `tabSales Order Item` soi2
              ON soi2.parent = tbc_st2.sales_order
            WHERE tbc_st2.parent = tor.name
              AND tbc_st2.name   = pi.bundle_configuration
              AND tbc_st2.parentfield = 'component_bundle_configurations'
              AND tbc_st2.activation_status = 'Completed'
              AND soi2.item_code = %(style)s
          )
          OR pi.item_code = %(style)s
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


def _load_last_ops_per_cell():
    return frappe.db.sql(
        """
        SELECT
          topclo.parent       AS tracking_order,
          topclo.physical_cell,
          topclo.operation    AS last_operation
        FROM `tabTracking Order Physical Cell Last Operation` topclo
        """,
        as_dict=True,
    )


def _load_operation_map():
    return frappe.db.sql(
        """
        SELECT
          om.parent         AS tracking_order,
          om.operation,
          om.next_operation
        FROM `tabOperation Map` om
        """,
        as_dict=True,
    )


# ======================================================================
#                             INDEX BUILDERS
# ======================================================================

def _index_scans(scan_rows):
    from collections import defaultdict

    scans_by_cell = defaultdict(list)
    scans_by_tor = defaultdict(list)
    scans_by_tor_op = defaultdict(list)
    scans_by_cell_tor_op = defaultdict(list)

    # To filter to PIs that reached last ops:
    scans_by_tor_pi = defaultdict(list)
    scans_by_cell_tor_op_pi = defaultdict(list)

    for r in scan_rows:
        cell = r["physical_cell"]
        op = r["operation"]
        tor = r["tracking_order"]
        ts = r["logged_time"]
        pi = r["pi_name"]

    # Skip incomplete rows
        if not (cell and op and tor and ts and pi):
            continue

        scans_by_cell[cell].append(r)
        scans_by_tor[tor].append(r)
        scans_by_tor_op[(tor, op)].append(r)
        scans_by_cell_tor_op[(cell, tor, op)].append(r)

        scans_by_tor_pi[(tor, pi)].append(r)
        scans_by_cell_tor_op_pi[(cell, tor, op, pi)].append(r)

    # Sort by timestamp once
    for d in (scans_by_cell, scans_by_tor, scans_by_tor_op, scans_by_cell_tor_op,
              scans_by_tor_pi, scans_by_cell_tor_op_pi):
        for k in d.keys():
            d[k].sort(key=lambda x: x["logged_time"] or datetime.min)

    return dict(
        scans_by_cell=scans_by_cell,
        scans_by_tor=scans_by_tor,
        scans_by_tor_op=scans_by_tor_op,
        scans_by_cell_tor_op=scans_by_cell_tor_op,
        scans_by_tor_pi=scans_by_tor_pi,
        scans_by_cell_tor_op_pi=scans_by_cell_tor_op_pi,
    )


def _graph_by_tracking_order(opmap_rows):
    from collections import defaultdict
    next_map = defaultdict(dict)
    ops_set = defaultdict(set)

    for r in opmap_rows:
        tor = r["tracking_order"]
        op = r.get("operation")
        nxt = r.get("next_operation")
        if op:
            ops_set[tor].add(op)
        if nxt:
            ops_set[tor].add(nxt)
        next_map[tor][op] = nxt

    return {tor: {"ops": ops_set.get(tor, set()), "next": next_map[tor]}
            for tor in next_map}


# ======================================================================
#                         PYTHON COMPUTATIONS
# ======================================================================

def _compute_tpt_by_cell(idx, last_op_map):
    result = []

    scans_by_cell = idx["scans_by_cell"]
    scans_by_cell_tor_op_pi = idx["scans_by_cell_tor_op_pi"]

    for cell, rows in scans_by_cell.items():
        if not rows:
            continue

        tors = {r["tracking_order"] for r in rows if r.get("tracking_order")}
        pis_that_reached = set()
        last_ts_candidates = []

        for tor in tors:
            last_op = last_op_map.get((tor, cell))
            if not last_op:
                continue

            pis_in_tor = {r["pi_name"] for r in rows if r["tracking_order"] == tor}
            for pi in pis_in_tor:
                logs = scans_by_cell_tor_op_pi.get((cell, tor, last_op, pi), [])
                if logs:
                    pis_that_reached.add(pi)
                    last_ts_candidates.append((logs[-1]["logged_time"], last_op))

        if not pis_that_reached:
            continue

        first_ts_candidates = [r["logged_time"] for r in rows if r["pi_name"] in pis_that_reached]
        first_ts = min(first_ts_candidates) if first_ts_candidates else None

        last_ts = None
        last_op_selected = None
        if last_ts_candidates:
            last_ts_candidates.sort(key=lambda x: x[0] or datetime.min)
            last_ts, last_op_selected = last_ts_candidates[-1]

        if not (first_ts and last_ts):
            continue

        tpt_seconds = (last_ts - first_ts).total_seconds()
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


def _compute_tpt_overall(idx, graph_by_tor):
    result = []

    scans_by_tor = idx["scans_by_tor"]
    scans_by_tor_op = idx["scans_by_tor_op"]

    for tor, tor_scans in scans_by_tor.items():
        if not tor_scans:
            continue

        g = graph_by_tor.get(tor) or {"ops": set(), "next": {}}
        ops = set(g.get("ops") or [])
        nxt = g.get("next") or {}

        next_values = {v for v in nxt.values() if v}
        first_ops = [op for op in ops if op and op not in next_values]
        last_ops = [op for op in ops if not nxt.get(op)]

        if not first_ops or not last_ops:
            continue

        pis_that_reached = set()
        for op in last_ops:
            for r in scans_by_tor_op.get((tor, op), []):
                pis_that_reached.add(r["pi_name"])

        if not pis_that_reached:
            continue

        first_ts_candidates = []
        for op in first_ops:
            for r in scans_by_tor_op.get((tor, op), []):
                if r["pi_name"] in pis_that_reached:
                    first_ts_candidates.append(r["logged_time"])
        first_ts = min(first_ts_candidates) if first_ts_candidates else None

        last_ts_candidates = []
        for op in last_ops:
            for r in scans_by_tor_op.get((tor, op), []):
                if r["pi_name"] in pis_that_reached:
                    last_ts_candidates.append(r["logged_time"])
        last_ts = max(last_ts_candidates) if last_ts_candidates else None

        if not (first_ts and last_ts):
            continue

        tpt_seconds = (last_ts - first_ts).total_seconds()
        result.append({
            "tracking_order": tor,
            "first_op": first_ops[0],
            "first_ts": first_ts,
            "last_op": last_ops[0],
            "last_ts": last_ts,
            "tpt_seconds": tpt_seconds,
            "tpt_hhmm": _fmt_hhmmss(tpt_seconds),
        })

    result.sort(key=lambda r: (r["tracking_order"] or ""))
    return result


# ======================================================================
#                             UTILITIES
# ======================================================================

def _csv_to_set(csv_str):
    if not csv_str:
        return set()
    return set(s.strip() for s in csv_str.split(",") if s and s.strip())


def _resolve_datetime_window(filters):
    """
    Returns (start_dt, end_dt) for isl.logged_time filtering.
    Precedence: date_range > date > today
    """
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
