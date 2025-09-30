# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe

# -------------------------
# Constants & small helpers
# -------------------------

# NOTE: If your "good" status is 'Passed' (not 'Pass'), update below accordingly.
GOOD_STATUSES   = ("Counted", "Activated", "Pass")
REJECT_STATUSES = ("QC Reject", "QC Recut", "SP Recut", "SP Reject")


def _chunked(seq, n=1000):
    """Yield chunks from seq of length n (for IN (...) batching)."""
    it = list(seq)
    for i in range(0, len(it), n):
        yield it[i:i + n]


def _date_predicate_and_params(filters, alias="soi"):
    """
    Return (predicate_sql, params) for Sales Order Item date filters.
    Uses DATE(soi.custom_ex_fty_date) BETWEEN ... if date_range is provided,
    otherwise YEAR(soi.custom_ex_fty_date) = current year.
    """
    if filters.get("date_range"):
        start, end = filters["date_range"]
        return (f"DATE({alias}.custom_ex_fty_date) BETWEEN %(start)s AND %(end)s",
                {"start": start, "end": end})
    else:
        from frappe.utils import now_datetime
        year = now_datetime().year
        return (f"YEAR({alias}.custom_ex_fty_date) = %(year)s", {"year": year})


def _fetch_valid_so_list(filters):
    """Return a list of SO names that (1) have FG items and (2) match the date predicate."""
    pred, p = _date_predicate_and_params(filters, alias="soi")
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT soi.parent AS so
        FROM `tabSales Order Item` soi
        INNER JOIN `tabItem` itm ON itm.name = soi.item_code
        WHERE soi.custom_ex_fty_date IS NOT NULL
          AND itm.custom_select_master = 'Finished Goods'
          AND {pred}
        """,
        p,
        as_dict=True,
    )
    return [r["so"] for r in rows]


def _fetch_valid_so_items(filters):
    """Return a set of (sales_order, item_code) pairs that pass FG + date predicate."""
    pred, p = _date_predicate_and_params(filters, alias="soi")
    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT soi.parent AS sales_order, soi.item_code
        FROM `tabSales Order Item` soi
        INNER JOIN `tabItem` itm ON itm.name = soi.item_code
        WHERE soi.custom_ex_fty_date IS NOT NULL
          AND itm.custom_select_master = 'Finished Goods'
          AND {pred}
        """,
        p,
        as_dict=True,
    )
    return {(r["sales_order"], r["item_code"]) for r in rows}


def _map_so_total_qty(so_list):
    """Return dict[so] -> total_qty for docstatus=1 Sales Orders."""
    if not so_list:
        return {}
    out = {}
    for chunk in _chunked(so_list):
        for r in frappe.db.sql(
            """
            SELECT name, total_qty
            FROM `tabSales Order`
            WHERE docstatus = 1 AND name IN %(names)s
            """,
            {"names": tuple(chunk)},
            as_dict=True,
        ):
            out[r["name"]] = float(r["total_qty"] or 0)
    return out


def _size_qty_by_so(so_name):
    """Dedup SOI to size level -> SUM(qty)."""
    rows = frappe.db.sql(
        """
        SELECT custom_size, SUM(qty) AS qty
        FROM `tabSales Order Item`
        WHERE parent = %(so)s
        GROUP BY custom_size
        """,
        {"so": so_name},
        as_dict=True,
    )
    return {r["custom_size"]: float(r["qty"] or 0) for r in rows}


def _size_qty_by_wo(wo_name):
    """WO size allocation -> SUM(work_order_allocated_qty)."""
    rows = frappe.db.sql(
        """
        SELECT size, SUM(work_order_allocated_qty) AS qty
        FROM `tabWork Order Line Item`
        WHERE parent = %(wo)s
        GROUP BY size
        """,
        {"wo": wo_name},
        as_dict=True,
    )
    return {r["size"]: float(r["qty"] or 0) for r in rows}


def _good_scan_set(pi_names, operation=None):
    """
    Return set of production_item that have at least one GOOD scan.
    If operation is provided, filter by that operation.
    """
    if not pi_names:
        return set()
    good = set()
    for chunk in _chunked(pi_names):
        params = {"pi": tuple(chunk)}
        op_sql = ""
        if operation:
            op_sql = " AND isl.operation = %(op)s"
            params["op"] = operation
        rows = frappe.db.sql(
            f"""
            SELECT DISTINCT isl.production_item
            FROM `tabItem Scan Log` isl
            WHERE isl.log_status = 'Completed'
              AND isl.status IN %(good)s
              AND isl.production_item IN %(pi)s
              {op_sql}
            """,
            {"good": GOOD_STATUSES, **params},
            as_dict=True,
        )
        good.update(r["production_item"] for r in rows)
    return good


def _reject_counts(pi_names, operation=None):
    """
    Return dict[production_item] -> reject_count.
    If operation is provided, filter by that operation.
    """
    if not pi_names:
        return {}
    out = {}
    for chunk in _chunked(pi_names):
        params = {"pi": tuple(chunk)}
        op_sql = ""
        if operation:
            op_sql = " AND isl.operation = %(op)s"
            params["op"] = operation
        rows = frappe.db.sql(
            f"""
            SELECT isl.production_item, COUNT(*) AS cnt
            FROM `tabItem Scan Log` isl
            WHERE isl.log_status = 'Completed'
              AND isl.status IN %(rej)s
              AND isl.production_item IN %(pi)s
              {op_sql}
            GROUP BY isl.production_item
            """,
            {"rej": REJECT_STATUSES, **params},
            as_dict=True,
        )
        for r in rows:
            out[r["production_item"]] = out.get(r["production_item"], 0) + int(r["cnt"] or 0)
    return out


# ---------------
# Report Entrypoint
# ---------------

def execute(filters=None):
    filters = filters or {}
    summary_so = get_summary_so(filters)
    summary_wo = get_summary_wo(filters)
    detail_so  = get_detail_so(filters.get("sales_order"))
    detail_wo  = get_detail_wo(filters.get("work_order"))

    # Script reports: columns & rows are empty; everything in "summary" for the viewer
    return [], [], None, None, [
        {"name": "summary_so", "data": summary_so or []},
        {"name": "summary_wo", "data": summary_wo or []},
        {"name": "detail_so", "data": detail_so or {}},
        {"name": "detail_wo", "data": detail_wo or {}},
    ]


# -------------------------
# Summaries (DB-light)
# -------------------------

def get_summary_so(filters):
    """Per-Sales Order summary for a selected operation — DB-light, Python rollup."""
    op = filters.get("operation")
    if not op:
        return []

    # (1) SOs that qualify by FG + date
    so_list = _fetch_valid_so_list(filters)
    if not so_list:
        return []

    # (2) Map SO -> total_qty
    so_total = _map_so_total_qty(so_list)

    # (3) Core PI rows at the selected operation (via Operation Map)
    core = []
    for chunk in _chunked(so_list):
        rows = frappe.db.sql(
            """
            SELECT
                tbc.sales_order  AS so_number,
                pi.name          AS pi_name,
                pi.quantity      AS pi_qty
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor
                ON tor.name = tbc.parent
            INNER JOIN `tabOperation Map` opm
                ON opm.parent = tor.name AND opm.operation = %(op)s
            LEFT JOIN `tabProduction Item` pi
                ON pi.tracking_order = tor.name
               AND pi.bundle_configuration = tbc.name
            LEFT JOIN `tabTracking Component` tc
                ON tc.name = pi.component AND tc.is_main = 1
            WHERE tbc.parentfield = 'component_bundle_configurations'
              AND tbc.sales_order IN %(sos)s
            """,
            {"op": op, "sos": tuple(chunk)},
            as_dict=True,
        )
        core.extend(rows)

    # (4) Dedup per PI in Python
    by_so = {}
    pi_all = set()
    for r in core:
        so = r["so_number"]
        pi = r["pi_name"]
        qty = float(r["pi_qty"] or 0)
        if not so or not pi:
            continue
        pi_all.add(pi)
        by_so.setdefault(so, {}).setdefault(pi, qty)

    # (5) Good & reject aggregates
    good = _good_scan_set(list(pi_all), operation=op)
    rej  = _reject_counts(list(pi_all), operation=op)

    # (6) Compose rows
    out = []
    for so in sorted(by_so.keys()):
        pis = by_so[so]
        completed = sum(qty for pi, qty in pis.items() if pi in good)
        rejected  = sum(rej.get(pi, 0) for pi in pis.keys())
        total_qty = float(so_total.get(so, 0))
        pending   = max(total_qty - completed - rejected, 0)
        if total_qty > 0:
            out.append({
                "so_number": so,
                "so_quantity": total_qty,
                "completed_units": completed,
                "rejected_units": rejected,
                "pending_units": pending,
            })
    return out


def get_summary_wo(filters):
    """Per-Work Order summary for a selected operation — DB-light, Python rollup."""
    op = filters.get("operation")
    if not op:
        return []

    # (1) Allowed (SO, item_code) pairs by FG + date
    allowed = _fetch_valid_so_items(filters)
    if not allowed:
        return []

    # (2) WO ↔ SO map and keep only allowed pairs
    rows_woso = frappe.db.sql(
        """
        SELECT woso.parent AS work_order, woso.sales_order, wo.production_item, wo.qty
        FROM `tabWork Order` wo
        INNER JOIN `tabWork Order Sales Orders` woso
            ON woso.parent = wo.name
        WHERE wo.docstatus = 1 AND woso.sales_order IS NOT NULL
        """,
        as_dict=True,
    )
    wo_keep = {}
    for r in rows_woso:
        key = (r["sales_order"], r["production_item"])
        if key in allowed:
            wo_keep[r["work_order"]] = {"qty": float(r["qty"] or 0)}

    if not wo_keep:
        return []

    # (3) Core PI rows per WO at the selected operation
    core = []
    for chunk in _chunked(list(wo_keep.keys())):
        rows = frappe.db.sql(
            """
            SELECT
                tbc.work_order   AS wo_number,
                pi.name          AS pi_name,
                pi.quantity      AS pi_qty
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor
                ON tor.name = tbc.parent
            INNER JOIN `tabOperation Map` opm
                ON opm.parent = tor.name AND opm.operation = %(op)s
            LEFT JOIN `tabProduction Item` pi
                ON pi.tracking_order = tor.name
               AND pi.bundle_configuration = tbc.name
            LEFT JOIN `tabTracking Component` tc
                ON tc.name = pi.component AND tc.is_main = 1
            WHERE tbc.parentfield = 'component_bundle_configurations'
              AND tbc.work_order IN %(wos)s
            """,
            {"op": op, "wos": tuple(chunk)},
            as_dict=True,
        )
        core.extend(rows)

    # (4) Dedup per PI in Python
    by_wo = {}
    pi_all = set()
    for r in core:
        wo  = r["wo_number"]
        pi  = r["pi_name"]
        qty = float(r["pi_qty"] or 0)
        if not wo or not pi:
            continue
        pi_all.add(pi)
        by_wo.setdefault(wo, {}).setdefault(pi, qty)

    # (5) Good & reject aggregates
    good = _good_scan_set(list(pi_all), operation=op)
    rej  = _reject_counts(list(pi_all), operation=op)

    # (6) Compose rows
    out = []
    for wo in sorted(by_wo.keys()):
        pis = by_wo[wo]
        completed = sum(qty for pi, qty in pis.items() if pi in good)
        rejected  = sum(rej.get(pi, 0) for pi in pis.keys())
        total_qty = float(wo_keep.get(wo, {}).get("qty", 0))
        pending   = max(total_qty - completed - rejected, 0)
        if total_qty > 0:
            out.append({
                "wo_number": wo,
                "wo_quantity": total_qty,
                "completed_units": completed,
                "rejected_units": rejected,
                "pending_units": pending,
            })
    return out


# -------------------------
# Details (DB-light)
# -------------------------

def get_detail_so(so_name):
    """SO details and metrics by (operation, size) — Python rollup."""
    if not so_name:
        return {}

    # Header details (unchanged shape)
    so_details = frappe.db.sql(
        """
        SELECT 
            so.name AS so_number,
            so.total_qty AS so_quantity,
            GROUP_CONCAT(DISTINCT DATE(soi.custom_ex_fty_date) ORDER BY soi.item_code SEPARATOR ' | ') AS ex_factory_date,
            GROUP_CONCAT(DISTINCT itm.brand ORDER BY itm.item_name SEPARATOR ' | ') AS fty_client,
            GROUP_CONCAT(DISTINCT itm.item_name ORDER BY itm.item_name SEPARATOR ' | ') AS product_family,
            GROUP_CONCAT(DISTINCT itm.name  ORDER BY itm.item_name SEPARATOR ' | ') AS fty_prod_id,
            GROUP_CONCAT(DISTINCT itm.name  ORDER BY itm.item_name SEPARATOR ' | ') AS style,
            GROUP_CONCAT(DISTINCT itm.custom_colour_code ORDER BY itm.item_name SEPARATOR ' | ') AS color,
            GROUP_CONCAT(DISTINCT itm.custom_material_composition ORDER BY itm.item_name SEPARATOR ' | ') AS material
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        INNER JOIN `tabItem` itm ON itm.name = soi.item_code AND itm.custom_select_master = 'Finished Goods'
        WHERE so.docstatus = 1 AND so.name = %(so)s
        GROUP BY so.name, so.total_qty
        """,
        {"so": so_name},
        as_dict=True,
    )
    if not so_details:
        return {}

    # Size capacity for this SO
    size_qty = _size_qty_by_so(so_name)

    # Core PI rows across all operations (dedup Operation Map per (order, operation))
    core = frappe.db.sql(
        """
        SELECT
            opm.operation     AS operation,
            tbc.size          AS size,
            pi.name           AS pi_name,
            pi.quantity       AS pi_qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor
            ON tor.name = tbc.parent
        INNER JOIN (
            SELECT parent, operation
            FROM `tabOperation Map`
            GROUP BY parent, operation
        ) opm
            ON opm.parent = tor.name
        LEFT JOIN `tabProduction Item` pi
            ON pi.tracking_order = tor.name
           AND pi.bundle_configuration = tbc.name
        LEFT JOIN `tabTracking Component` tc
            ON tc.name = pi.component AND tc.is_main = 1
        WHERE tbc.parentfield = 'component_bundle_configurations'
          AND tbc.sales_order = %(so)s
        """,
        {"so": so_name},
        as_dict=True,
    )

    # Dedup PI per (operation, size)
    by_key = {}   # (op, size) -> { pi: qty }
    pi_all = set()
    for r in core:
        op   = r["operation"]
        size = r["size"]
        pi   = r["pi_name"]
        qty  = float(r["pi_qty"] or 0)
        if not op or not size or not pi:
            continue
        pi_all.add(pi)
        by_key.setdefault((op, size), {}).setdefault(pi, qty)

    # Good & rejects across all operations
    good = _good_scan_set(list(pi_all))
    rej  = _reject_counts(list(pi_all))

    metrics = []
    for (op, size), pis in sorted(by_key.items()):
        completed = sum(qty for pi, qty in pis.items() if pi in good)
        rejected  = sum(rej.get(pi, 0) for pi in pis.keys())
        cap = float(size_qty.get(size, 0))
        metrics.append({
            "operation": op,
            "size": size,
            "size_qty": cap,
            "completed_units": completed,
            "rejected_units": rejected,
            "pending_units": max(cap - completed - rejected, 0),
        })

    return {"details": so_details[0], "metrics_by_op": metrics}


def get_detail_wo(wo_name):
    """WO details and metrics by (operation, size) — Python rollup."""
    if not wo_name:
        return {}

    # Header details (unchanged shape)
    wo_details = frappe.db.sql(
        """
        SELECT 
            wo.name AS wo_number,
            wo.qty AS wo_quantity,        
            GROUP_CONCAT(DISTINCT woli.sales_order ORDER BY woli.sales_order SEPARATOR ' | ') AS sales_order,
            GROUP_CONCAT(DISTINCT CONVERT(woli.wo_allocated_qty, SIGNED) ORDER BY woli.sales_order SEPARATOR ' | ') AS wo_allocated_qty,
            GROUP_CONCAT(DISTINCT DATE(soi.custom_ex_fty_date) ORDER BY woli.sales_order SEPARATOR ' | ') AS ex_factory_date,
            GROUP_CONCAT(DISTINCT itm.brand ORDER BY woli.sales_order SEPARATOR ' | ') AS fty_client,
            GROUP_CONCAT(DISTINCT itm.item_name ORDER BY woli.sales_order SEPARATOR ' | ') AS product_family,
            GROUP_CONCAT(DISTINCT itm.name  ORDER BY woli.sales_order SEPARATOR ' | ') AS fty_prod_id,
            GROUP_CONCAT(DISTINCT itm.name  ORDER BY woli.sales_order SEPARATOR ' | ') AS style,
            GROUP_CONCAT(DISTINCT itm.custom_colour_code ORDER BY woli.sales_order SEPARATOR ' | ') AS color,
            GROUP_CONCAT(DISTINCT itm.custom_material_composition ORDER BY woli.sales_order SEPARATOR ' | ') AS material
        FROM `tabWork Order` wo
        INNER JOIN (
            SELECT parent AS work_order, sales_order, SUM(work_order_allocated_qty) AS wo_allocated_qty
            FROM `tabWork Order Line Item`
            GROUP BY parent, sales_order
        ) woli ON woli.work_order = wo.name
        INNER JOIN (
            SELECT parent, custom_ex_fty_date, item_code
            FROM `tabSales Order Item`
            GROUP BY parent, custom_ex_fty_date, item_code
        ) soi ON soi.parent = woli.sales_order AND soi.item_code = wo.production_item
        INNER JOIN `tabItem` itm ON itm.name = wo.production_item AND itm.custom_select_master = 'Finished Goods'
        WHERE wo.docstatus = 1 AND wo.name = %(wo)s
        GROUP BY wo.name, wo.qty
        """,
        {"wo": wo_name},
        as_dict=True,
    )
    if not wo_details:
        return {}

    # Size capacity from WOLI
    size_qty = _size_qty_by_wo(wo_name)

    # Core PI rows across all operations (dedup Operation Map per (order, operation))
    core = frappe.db.sql(
        """
        SELECT
            opm.operation     AS operation,
            tbc.size          AS size,
            pi.name           AS pi_name,
            pi.quantity       AS pi_qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor
            ON tor.name = tbc.parent
        INNER JOIN (
            SELECT parent, operation
            FROM `tabOperation Map`
            GROUP BY parent, operation
        ) opm
            ON opm.parent = tor.name
        LEFT JOIN `tabProduction Item` pi
            ON pi.tracking_order = tor.name
           AND pi.bundle_configuration = tbc.name
        LEFT JOIN `tabTracking Component` tc
            ON tc.name = pi.component AND tc.is_main = 1
        WHERE tbc.parentfield = 'component_bundle_configurations'
          AND tbc.work_order = %(wo)s
        """,
        {"wo": wo_name},
        as_dict=True,
    )

    # Dedup PI per (operation, size)
    by_key = {}
    pi_all = set()
    for r in core:
        op   = r["operation"]
        size = r["size"]
        pi   = r["pi_name"]
        qty  = float(r["pi_qty"] or 0)
        if not op or not size or not pi:
            continue
        pi_all.add(pi)
        by_key.setdefault((op, size), {}).setdefault(pi, qty)

    good = _good_scan_set(list(pi_all))
    rej  = _reject_counts(list(pi_all))

    metrics = []
    for (op, size), pis in sorted(by_key.items()):
        completed = sum(qty for pi, qty in pis.items() if pi in good)
        rejected  = sum(rej.get(pi, 0) for pi in pis.keys())
        cap = float(size_qty.get(size, 0))
        metrics.append({
            "operation": op,
            "size": size,
            "size_qty": cap,
            "completed_units": completed,
            "rejected_units": rejected,
            "pending_units": max(cap - completed - rejected, 0),
        })

    return {"details": wo_details[0], "metrics_by_op": metrics}
