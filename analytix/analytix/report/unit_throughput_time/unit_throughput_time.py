# Copyright (c) 2025,
# CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta
from frappe.utils import nowdate, getdate

ALLOWED_STATUSES = ("Counted", "Activated", "Pass", "QC Reject", "SP Reject")


def execute(filters=None):
    """
    Unit Throughput Time (no complex SQL; Python does the work)

    Returns message payload with two datasets:
      - {"name": "by_cell",   "data": [{ physical_cell, first_ts, last_op, last_ts, tpt_seconds, tpt_hhmm }]}
      - {"name": "overall",   "data": [{ tracking_order, first_op, first_ts, last_op, last_ts, tpt_seconds, tpt_hhmm }]}

    Filters (all optional):
      - date (YYYY-MM-DD) OR date_range = [from_date, to_date]   (date_range has precedence)
      - physical_cell_csv (CSV list)
      - operation_csv     (CSV list)
    """
    filters = filters or {}

    # --------- Resolve date window ---------
    start_dt, end_dt = _resolve_datetime_window(filters)

    # --------- CSV filters -> sets ---------
    pc_filter = _csv_to_set(filters.get("physical_cell_csv"))
    op_filter = _csv_to_set(filters.get("operation_csv"))

    # --------- Load data with simple queries ---------
    # 1) Scan rows
    scan_rows = _load_scans(start_dt, end_dt, pc_filter, op_filter)

    if not scan_rows:
        # Empty datasets
        return [], [], None, None, [
            {"name": "by_cell", "data": []},
            {"name": "overall", "data": []},
        ]

    # 2) Last operation per (tracking_order, physical_cell)
    topclo_rows = _load_last_ops_per_cell()
    # 3) Operation graph (operation -> next_operation) per tracking_order
    opmap_rows  = _load_operation_map()

    # --------- Build indices in Python ---------
    # scans_by_cell, scans_by_tor, scans_by_tor_op, scans_by_cell_tor_op, etc.
    idx = _index_scans(scan_rows)

    # mapping (tracking_order, physical_cell) -> last_operation
    last_op_map = {}
    for r in topclo_rows:
        last_op_map[(r["tracking_order"], r["physical_cell"])] = r["last_operation"]

    # operation graph per TOR
    graph_by_tor = _graph_by_tracking_order(opmap_rows)

    # --------- 1) TPT by PHYSICAL CELL (Python) ---------
    by_cell = _compute_tpt_by_cell(idx, last_op_map)

    # --------- 2) TPT for WHOLE PROCESS MAP (by TOR) (Python) ---------
    overall = _compute_tpt_overall(idx, graph_by_tor)

    return [], [], None, None, [
        {"name": "by_cell", "data": by_cell},
        {"name": "overall", "data": overall},
    ]


# ======================================================================
#                             LOADERS
# ======================================================================

def _load_scans(start_dt, end_dt, pc_filter, op_filter):
    """
    Minimal query to fetch scan facts. We filter by date + statuses here.
    Optional FIND_IN_SET filters for cell/op if provided.
    """
    conds = [
        "isl.log_status = 'Completed'",
        f"isl.status IN {sql_tuple(ALLOWED_STATUSES)}",
        "isl.logged_time >= %(start_dt)s",
        "isl.logged_time <  %(end_dt)s",
    ]
    params = {"start_dt": start_dt, "end_dt": end_dt}

    if pc_filter:
        conds.append("FIND_IN_SET(isl.physical_cell, %(pc_csv)s)")
        params["pc_csv"] = ",".join(sorted(pc_filter))

    if op_filter:
        conds.append("FIND_IN_SET(isl.operation, %(op_csv)s)")
        params["op_csv"] = ",".join(sorted(op_filter))

    where_sql = " AND ".join(conds)

    rows = frappe.db.sql(
        f"""
        SELECT
          isl.physical_cell,
          isl.operation,
          isl.logged_time,
          tc.parent AS tracking_order
        FROM `tabItem Scan Log` isl
        LEFT JOIN `tabProduction Item`  pi ON pi.name = isl.production_item
        LEFT JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        WHERE {where_sql}
        """,
        params,
        as_dict=True,
    )
    return rows


def _load_last_ops_per_cell():
    """
    Load last operation per (tracking_order, physical_cell).
    """
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
    """
    Fetch the operation links (operation -> next_operation) for each tracking_order.
    """
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
    """
    Build several helpful indices for fast Python computations.
    """
    from collections import defaultdict

    scans_by_cell = defaultdict(list)              # cell -> [row,...]
    scans_by_tor  = defaultdict(list)              # tor  -> [row,...]
    scans_by_tor_op = defaultdict(list)            # (tor, op) -> [row,...]
    scans_by_cell_tor_op = defaultdict(list)       # (cell, tor, op) -> [row,...]

    for r in scan_rows:
        cell = r["physical_cell"]
        op   = r["operation"]
        tor  = r["tracking_order"]
        ts   = r["logged_time"]

        if not (cell and op and tor and ts):
            # skip incomplete rows
            continue

        scans_by_cell[cell].append(r)
        scans_by_tor[tor].append(r)
        scans_by_tor_op[(tor, op)].append(r)
        scans_by_cell_tor_op[(cell, tor, op)].append(r)

    # Sort each list by timestamp once (ascending)
    for d in (scans_by_cell, scans_by_tor, scans_by_tor_op, scans_by_cell_tor_op):
        for k in d.keys():
            d[k].sort(key=lambda x: x["logged_time"] or datetime.min)

    return dict(
        scans_by_cell=scans_by_cell,
        scans_by_tor=scans_by_tor,
        scans_by_tor_op=scans_by_tor_op,
        scans_by_cell_tor_op=scans_by_cell_tor_op,
    )


def _graph_by_tracking_order(opmap_rows):
    """
    Build operation graphs per TOR:
      graph_by_tor[tor] = {
        "ops": set([...]),
        "next": { op -> next_op (or None) }   # last nodes have None or missing
      }
    """
    from collections import defaultdict

    next_map = defaultdict(dict)
    ops_set  = defaultdict(set)

    for r in opmap_rows:
        tor = r["tracking_order"]
        op = r.get("operation")
        nxt = r.get("next_operation")
        if op:
            ops_set[tor].add(op)
        if nxt:
            ops_set[tor].add(nxt)
        # Only one next per row; last ops will either be absent in values or have nxt None
        next_map[tor][op] = nxt

    out = {}
    for tor in next_map:
        out[tor] = {
            "ops": ops_set.get(tor, set()),
            "next": next_map[tor],
        }
    return out


# ======================================================================
#                         PYTHON COMPUTATIONS
# ======================================================================

def _compute_tpt_by_cell(idx, last_op_map):
    """
    Per physical cell:
      first_ts := earliest scan in that cell (any op, any tor)
      last_ts  := across all TORs that touched that cell, look up the last_operation configured
                  for (tor, cell); then take the latest scan in that (cell, tor, last_operation)
      tpt      := last_ts - first_ts
    """
    result = []
    scans_by_cell = idx["scans_by_cell"]
    scans_by_cell_tor_op = idx["scans_by_cell_tor_op"]

    for cell, rows in scans_by_cell.items():
        # earliest in this cell
        first_ts = rows[0]["logged_time"] if rows else None

        # find all TORs that touched this cell
        tors = set(r["tracking_order"] for r in rows if r.get("tracking_order"))

        # for each TOR, find its configured last op for this cell, then get the latest scan at that op
        last_ts_candidates = []
        last_op_selected = None

        for tor in tors:
            last_op = last_op_map.get((tor, cell))
            if not last_op:
                continue
            k = (cell, tor, last_op)
            logs = scans_by_cell_tor_op.get(k, [])
            if logs:
                # logs sorted asc by ts; pick latest
                last = logs[-1]
                last_ts_candidates.append((last["logged_time"], last_op))

        if last_ts_candidates:
            last_ts_candidates.sort(key=lambda x: x[0] or datetime.min)
            last_ts, last_op_selected = last_ts_candidates[-1]
        else:
            last_ts, last_op_selected = (None, None)

        tpt_seconds = None
        if first_ts and last_ts:
            tpt_seconds = (last_ts - first_ts).total_seconds()

        result.append({
            "physical_cell": cell,
            "first_ts": first_ts,
            "last_op": last_op_selected,
            "last_ts": last_ts,
            "tpt_seconds": tpt_seconds,
            "tpt_hhmm": _fmt_hhmmss(tpt_seconds) if tpt_seconds is not None else "",
        })

    # stable order by cell
    result.sort(key=lambda r: (r["physical_cell"] or ""))
    return result


def _compute_tpt_overall(idx, graph_by_tor):
    """
    For each TOR:
      first_ops := ops that never appear as someone's next (i.e., sources)
      last_ops  := ops whose next is NULL/None or missing (i.e., sinks)
      first_ts  := earliest scan at any op in first_ops
      last_ts   := latest  scan at any op in last_ops
      tpt       := last_ts - first_ts
    """
    result = []
    scans_by_tor = idx["scans_by_tor"]
    scans_by_tor_op = idx["scans_by_tor_op"]

    for tor, tor_scans in scans_by_tor.items():
        if not tor_scans:
            continue

        g = graph_by_tor.get(tor) or {"ops": set(), "next": {}}
        ops = set(g.get("ops") or [])
        nxt = g.get("next") or {}

        # derive first_ops (ops not present as any next_operation)
        next_values = set([v for v in nxt.values() if v])
        first_ops = [op for op in ops if op and op not in next_values]
        if not first_ops and ops:
            # Fallback: if graph incomplete, use min(op) to have a deterministic seed
            first_ops = [sorted(ops)[0]]

        # derive last_ops (ops whose next is None or absent)
        last_ops = [op for op in ops if not nxt.get(op)]
        if not last_ops and ops:
            last_ops = [sorted(ops)[-1]]

        # compute first_ts = earliest across first_ops
        first_ts_candidates = []
        for op in first_ops:
            rows = scans_by_tor_op.get((tor, op), [])
            if rows:
                first_ts_candidates.append(rows[0]["logged_time"])
        first_ts = min(first_ts_candidates) if first_ts_candidates else None

        # compute last_ts = latest across last_ops
        last_ts_candidates = []
        for op in last_ops:
            rows = scans_by_tor_op.get((tor, op), [])
            if rows:
                last_ts_candidates.append(rows[-1]["logged_time"])
        last_ts = max(last_ts_candidates) if last_ts_candidates else None

        tpt_seconds = None
        if first_ts and last_ts:
            tpt_seconds = (last_ts - first_ts).total_seconds()

        result.append({
            "tracking_order": tor,
            "first_op": first_ops[0] if first_ops else None,
            "first_ts": first_ts,
            "last_op": last_ops[0] if last_ops else None,
            "last_ts": last_ts,
            "tpt_seconds": tpt_seconds,
            "tpt_hhmm": _fmt_hhmmss(tpt_seconds) if tpt_seconds is not None else "",
        })

    # stable order by TOR
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
    """
    Render a Python tuple of strings as a SQL-safe IN list without double quoting.
    """
    # e.g. ('A','B','C')
    return "(" + ",".join([frappe.db.escape(s) for s in py_tuple]) + ")"


def _fmt_hhmmss(seconds):
    if seconds is None or seconds < 0:
        return ""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
