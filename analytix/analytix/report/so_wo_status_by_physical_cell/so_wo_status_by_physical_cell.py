# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime


def execute(filters=None):
    filters = filters or {}
    summary_so = get_summary_so_by_cell(filters)
    summary_wo = get_summary_wo_by_cell(filters)
    detail_so = get_detail_so_by_cell(filters.get("sales_order"))
    detail_wo = get_detail_wo_by_cell(filters.get("work_order"))

    return [], [], None, None, [
        {"name": "summary_so", "data": summary_so or []},
        {"name": "summary_wo", "data": summary_wo or []},
        {"name": "detail_so", "data": detail_so or {}},
        {"name": "detail_wo", "data": detail_wo or {}},
    ]


def _build_date_conditions(filters, params, alias="soi"):
    conds = []
    if filters.get("date_range"):
        start, end = filters["date_range"]
        conds.append(f"DATE({alias}.custom_ex_fty_date) BETWEEN %(start)s AND %(end)s")
        params.update({"start": start, "end": end})
    else:
        year = now_datetime().year
        conds.append(f"YEAR({alias}.custom_ex_fty_date) = %(year)s")
        params["year"] = year
    return conds


# ======================
# SUMMARY QUERIES (NO WIP)
# ======================

def get_summary_so_by_cell(filters):
    if not filters.get("physical_cell"):
        return []

    params = {"physical_cell": filters["physical_cell"]}
    so_conds = ["so.docstatus = 1"]
    so_where = " AND ".join(so_conds)
    soi_date_conds = _build_date_conditions(filters, params, alias="soi")
    soi_date_where = " AND ".join(soi_date_conds) if soi_date_conds else "1=1"

    return frappe.db.sql(
        f"""
        SELECT
            so.name AS so_number,
            so.total_qty AS so_quantity,
            COALESCE(sa.completed_units, 0) AS completed_units,
            COALESCE(sa.rejected_units, 0) AS rejected_units,
            GREATEST(
                so.total_qty - COALESCE(sa.completed_units, 0) - COALESCE(sa.rejected_units, 0),
                0
            ) AS pending_units
        FROM `tabSales Order` so
        INNER JOIN (
            SELECT DISTINCT soi.parent
            FROM `tabSales Order Item` soi
            INNER JOIN `tabItem` itm ON itm.name = soi.item_code
            WHERE soi.custom_ex_fty_date IS NOT NULL
              AND itm.custom_select_master = 'Finished Goods'
              AND {soi_date_where}
        ) soi_ok ON soi_ok.parent = so.name
        LEFT JOIN (
            SELECT 
                tbc.sales_order,
                SUM(CASE 
                    WHEN isl.status IN ('Counted','Activated','Pass') 
                    THEN pi.quantity ELSE 0 
                END) AS completed_units,
                COUNT(CASE 
                    WHEN isl.status IN ('QC Reject','SP Reject')
                    THEN 1
                END) AS rejected_units
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
            INNER JOIN `tabTracking Order Physical Cell Last Operation` topclo
                ON topclo.parent = tor.name AND topclo.physical_cell = %(physical_cell)s
            INNER JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl 
                ON isl.production_item = pi.name 
                AND isl.operation = topclo.operation
                AND isl.log_status = 'Completed'
                AND isl.status IN ('Counted','Activated','Pass','QC Reject','SP Reject')
            WHERE tbc.parentfield = 'component_bundle_configurations' 
              AND tbc.activation_status = 'Completed' 
              AND tbc.sales_order IS NOT NULL
            GROUP BY tbc.sales_order
        ) sa ON sa.sales_order = so.name
        WHERE {so_where}
        HAVING so_quantity > 0
        ORDER BY so.name
        """,
        params,
        as_dict=True,
    )


def get_summary_wo_by_cell(filters):
    if not filters.get("physical_cell"):
        return []

    params = {"physical_cell": filters["physical_cell"]}
    wo_conds = ["wo.docstatus = 1"]
    wo_where = " AND ".join(wo_conds)
    soi_date_conds = _build_date_conditions(filters, params, alias="soi")
    soi_date_where = " AND ".join(soi_date_conds) if soi_date_conds else "1=1"

    return frappe.db.sql(
        f"""
        SELECT
            wo.name AS wo_number,
            wo.qty AS wo_quantity,
            COALESCE(sa.completed_units, 0) AS completed_units,
            COALESCE(sa.rejected_units, 0) AS rejected_units,
            GREATEST(
                wo.qty - COALESCE(sa.completed_units, 0) - COALESCE(sa.rejected_units, 0),
                0
            ) AS pending_units
        FROM `tabWork Order` wo
        INNER JOIN (
            SELECT parent AS work_order, sales_order
            FROM `tabWork Order Sales Orders`
            WHERE sales_order IS NOT NULL
            GROUP BY parent, sales_order
        ) woso ON woso.work_order = wo.name
        INNER JOIN (
            SELECT DISTINCT soi.parent AS sales_order, soi.item_code
            FROM `tabSales Order Item` soi
            INNER JOIN `tabItem` itm ON itm.name = soi.item_code
            WHERE soi.custom_ex_fty_date IS NOT NULL
              AND itm.custom_select_master = 'Finished Goods'
              AND {soi_date_where}
        ) soi_ok ON soi_ok.sales_order = woso.sales_order AND soi_ok.item_code = wo.production_item
        LEFT JOIN (
            SELECT 
                tbc.work_order,
                SUM(CASE 
                    WHEN isl.status IN ('Counted','Activated','Pass') 
                    THEN pi.quantity ELSE 0 
                END) AS completed_units,
                COUNT(CASE 
                    WHEN isl.status IN ('QC Reject','SP Reject') 
                    THEN 1
                END) AS rejected_units
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
            INNER JOIN `tabTracking Order Physical Cell Last Operation` topclo
                ON topclo.parent = tor.name AND topclo.physical_cell = %(physical_cell)s
            INNER JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl 
                ON isl.production_item = pi.name 
                AND isl.operation = topclo.operation
                AND isl.log_status = 'Completed'
                AND isl.status IN ('Counted','Activated','Pass','QC Reject','SP Reject')
            WHERE tbc.parentfield = 'component_bundle_configurations' 
              AND tbc.activation_status = 'Completed' 
              AND tbc.work_order IS NOT NULL
            GROUP BY tbc.work_order
        ) sa ON sa.work_order = wo.name
        WHERE {wo_where}
        HAVING wo_quantity > 0
        ORDER BY wo.name
        """,
        params,
        as_dict=True,
    )


# ======================
# DETAIL QUERIES (WITH WIP)
# ======================

def get_detail_so_by_cell(so_name):
    if not so_name:
        return {}

    so_details = frappe.db.sql("""
        SELECT 
            so.name AS so_number,
            so.total_qty AS so_quantity,
            GROUP_CONCAT(DISTINCT DATE(soi.custom_ex_fty_date) ORDER BY soi.item_code SEPARATOR ' | ') AS ex_factory_date,
            GROUP_CONCAT(DISTINCT itm.brand ORDER BY itm.item_name SEPARATOR ' | ') AS fty_client,
            GROUP_CONCAT(DISTINCT itm.item_name ORDER BY itm.item_name SEPARATOR ' | ') AS product_family,
            GROUP_CONCAT(DISTINCT itm.name ORDER BY itm.item_name SEPARATOR ' | ') AS fty_prod_id,
            GROUP_CONCAT(DISTINCT itm.name ORDER BY itm.item_name SEPARATOR ' | ') AS style,
            GROUP_CONCAT(DISTINCT itm.custom_colour_code ORDER BY itm.item_name SEPARATOR ' | ') AS color,
            GROUP_CONCAT(DISTINCT itm.custom_material_composition ORDER BY itm.item_name SEPARATOR ' | ') AS material
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        INNER JOIN `tabItem` itm ON itm.name = soi.item_code AND itm.custom_select_master = 'Finished Goods'
        WHERE so.name = %(so_name)s AND so.docstatus = 1
        GROUP BY so.name, so.total_qty
    """, {"so_name": so_name}, as_dict=True)

    if not so_details:
        return {}

    size_qty_list = frappe.db.sql("""
        SELECT custom_size, SUM(qty) AS qty
        FROM `tabSales Order Item`
        WHERE parent = %(so_name)s
        GROUP BY custom_size
    """, {"so_name": so_name}, as_dict=True)
    size_qty_map = {row.custom_size or "": row.qty for row in size_qty_list}
    sizes = list(size_qty_map.keys())

    if not sizes:
        return {"details": so_details[0], "metrics_by_cell": []}

    op_links = frappe.db.sql("""
        SELECT DISTINCT tor.name AS tracking_order, opm.operation, opm.next_operation
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name
        INNER JOIN `tabCut Kit Plan Bundle Details` ckpbd ON ckpbd.production_item_id = pi.name
        INNER JOIN `tabOperation Map` opm ON opm.parent = ckpbd.parent
        WHERE tbc.sales_order = %(so_name)s 
          AND tbc.parentfield = 'component_bundle_configurations' 
          AND tbc.activation_status = 'Completed'
    """, {"so_name": so_name}, as_dict=True)

    tor_ops = {}
    for row in op_links:
        tor = row.tracking_order
        if tor not in tor_ops:
            tor_ops[tor] = []
        tor_ops[tor].append((row.operation, row.next_operation))

    tor_seq = {}
    for tor, links in tor_ops.items():
        op_to_next = {}
        all_ops = set()
        for op, nxt in links:
            all_ops.add(op)
            if nxt:
                all_ops.add(nxt)
            op_to_next[op] = nxt

        next_ops = set(op_to_next.values())
        first_ops = [op for op in all_ops if op not in next_ops]
        seq = []
        for start in first_ops:
            cur = start
            while cur:
                seq.append(cur)
                cur = op_to_next.get(cur)
        tor_seq[tor] = seq

    cell_ops = frappe.db.sql("""
        SELECT DISTINCT topclo.physical_cell, topclo.parent AS tracking_order
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabTracking Order Physical Cell Last Operation` topclo ON topclo.parent = tor.name
        WHERE tbc.sales_order = %(so_name)s 
          AND tbc.parentfield = 'component_bundle_configurations' 
          AND tbc.activation_status = 'Completed'
    """, {"so_name": so_name}, as_dict=True)

    cell_first_last = {}
    for row in cell_ops:
        cell = row.physical_cell
        tor = row.tracking_order
        seq = tor_seq.get(tor, [])
        if seq:
            cell_first_last[cell] = {"first": seq[0], "last": seq[-1]}

    if not cell_first_last:
        return {"details": so_details[0], "metrics_by_cell": []}

    cells = list(cell_first_last.keys())
    all_operations = set()
    for ops in cell_first_last.values():
        all_operations.update([ops["first"], ops["last"]])

    if not all_operations:
        scan_logs = []
    else:
        scan_logs = frappe.db.sql("""
            SELECT
                isl.physical_cell,
                tbc.size,
                pi.quantity AS pi_qty,
                isl.status,
                isl.operation
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
            INNER JOIN `tabProduction Item` pi 
                ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl 
                ON isl.production_item = pi.name
                AND isl.log_status = 'Completed'
                AND isl.status IN ('Counted','Activated','Pass','QC Reject','SP Reject')
                AND isl.operation IN %(operations)s
                AND isl.physical_cell IN %(cells)s
            WHERE tbc.sales_order = %(sales_order)s
              AND tbc.parentfield = 'component_bundle_configurations' 
              AND tbc.activation_status = 'Completed'
        """, {
            "operations": list(all_operations),
            "cells": cells,
            "sales_order": so_name
        }, as_dict=True)

    from collections import defaultdict
    cell_op_size_completed = defaultdict(int)
    cell_op_size_rejected = defaultdict(int)
    for log in scan_logs:
        key = (log.physical_cell, log.operation, log.size or "")
        if log.status in ('Counted', 'Activated', 'Pass'):
            cell_op_size_completed[key] += log.pi_qty or 0
        elif log.status in ('QC Reject','SP Reject'):  # NEW
            cell_op_size_rejected[key] += log.pi_qty or 0   

    metrics_by_cell = []
    for cell in cells:
        first_op = cell_first_last[cell]["first"]
        last_op = cell_first_last[cell]["last"]
        for size in sizes:
            total_qty = size_qty_map[size]
            completed_first = cell_op_size_completed.get((cell, first_op, size), 0)
            completed_last = cell_op_size_completed.get((cell, last_op, size), 0)
            wip = max(0, completed_first - completed_last)
            completed = completed_last
            rejected = cell_op_size_rejected.get((cell, last_op, size), 0)
            pending = max(total_qty - completed, 0)
            completion_pct = min((completed / total_qty) * 100, 100.0) if total_qty > 0 else 0.0

            metrics_by_cell.append({
                "physical_cell": cell,
                "size": size,
                "size_qty": total_qty,
                "completed_units": completed,
                "rejected_units": rejected,
                "pending_units": pending,
                "completion_pct": round(completion_pct, 1),
                "wip": wip
            })

    metrics_by_cell.sort(key=lambda x: (x["physical_cell"], x["size"]))
    return {
        "details": so_details[0],
        "metrics_by_cell": metrics_by_cell
    }


def get_detail_wo_by_cell(wo_name):
    if not wo_name:
        return {}

    wo_details = frappe.db.sql("""
        SELECT 
            wo.name AS wo_number,
            wo.qty AS wo_quantity,        
            GROUP_CONCAT(DISTINCT woli.sales_order ORDER BY woli.sales_order SEPARATOR ' | ') AS sales_order,
            GROUP_CONCAT(DISTINCT CONVERT(woli.wo_allocated_qty, SIGNED) ORDER BY woli.sales_order SEPARATOR ' | ') AS wo_allocated_qty,
            GROUP_CONCAT(DISTINCT DATE(soi.custom_ex_fty_date) ORDER BY woli.sales_order SEPARATOR ' | ') AS ex_factory_date,
            GROUP_CONCAT(DISTINCT itm.brand ORDER BY woli.sales_order SEPARATOR ' | ') AS fty_client,
            GROUP_CONCAT(DISTINCT itm.item_name ORDER BY woli.sales_order SEPARATOR ' | ') AS product_family,
            GROUP_CONCAT(DISTINCT itm.name ORDER BY woli.sales_order SEPARATOR ' | ') AS fty_prod_id,
            GROUP_CONCAT(DISTINCT itm.name ORDER BY woli.sales_order SEPARATOR ' | ') AS style,
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
        WHERE wo.name = %(wo_name)s AND wo.docstatus = 1
        GROUP BY wo.name, wo.qty
    """, {"wo_name": wo_name}, as_dict=True)

    if not wo_details:
        return {}

    size_qty_list = frappe.db.sql("""
        SELECT size, SUM(work_order_allocated_qty) AS qty
        FROM `tabWork Order Line Item`
        WHERE parent = %(wo_name)s
        GROUP BY size
    """, {"wo_name": wo_name}, as_dict=True)
    size_qty_map = {row.size or "": row.qty for row in size_qty_list}
    sizes = list(size_qty_map.keys())

    if not sizes:
        return {"details": wo_details[0], "metrics_by_cell": []}

    op_links = frappe.db.sql("""
        SELECT DISTINCT tor.name AS tracking_order, opm.operation, opm.next_operation
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabOperation Map` opm ON opm.parent = tor.name
        WHERE tbc.work_order = %(wo_name)s 
          AND tbc.parentfield = 'component_bundle_configurations' 
          AND tbc.activation_status = 'Completed'
    """, {"wo_name": wo_name}, as_dict=True)

    tor_ops = {}
    for row in op_links:
        tor = row.tracking_order
        if tor not in tor_ops:
            tor_ops[tor] = []
        tor_ops[tor].append((row.operation, row.next_operation))

    tor_seq = {}
    for tor, links in tor_ops.items():
        op_to_next = {}
        all_ops = set()
        for op, nxt in links:
            all_ops.add(op)
            if nxt:
                all_ops.add(nxt)
            op_to_next[op] = nxt

        next_ops = set(op_to_next.values())
        first_ops = [op for op in all_ops if op not in next_ops]
        seq = []
        for start in first_ops:
            cur = start
            while cur:
                seq.append(cur)
                cur = op_to_next.get(cur)
        tor_seq[tor] = seq

    cell_ops = frappe.db.sql("""
        SELECT DISTINCT topclo.physical_cell, topclo.parent AS tracking_order
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabTracking Order Physical Cell Last Operation` topclo ON topclo.parent = tor.name
        WHERE tbc.work_order = %(wo_name)s 
          AND tbc.parentfield = 'component_bundle_configurations' 
          AND tbc.activation_status = 'Completed'
    """, {"wo_name": wo_name}, as_dict=True)

    cell_first_last = {}
    for row in cell_ops:
        cell = row.physical_cell
        tor = row.tracking_order
        seq = tor_seq.get(tor, [])
        if seq:
            cell_first_last[cell] = {"first": seq[0], "last": seq[-1]}

    if not cell_first_last:
        return {"details": wo_details[0], "metrics_by_cell": []}

    cells = list(cell_first_last.keys())
    all_operations = set()
    for ops in cell_first_last.values():
        all_operations.update([ops["first"], ops["last"]])

    if not all_operations:
        scan_logs = []
    else:
        scan_logs = frappe.db.sql("""
            SELECT
                isl.physical_cell,
                tbc.size,
                pi.quantity AS pi_qty,
                isl.status,
                isl.operation
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
            INNER JOIN `tabProduction Item` pi 
                ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl 
                ON isl.production_item = pi.name
                AND isl.log_status = 'Completed'
                AND isl.status IN ('Counted','Activated','Pass','QC Reject','SP Reject')
                AND isl.operation IN %(operations)s
                AND isl.physical_cell IN %(cells)s
            WHERE tbc.work_order = %(work_order)s
              AND tbc.parentfield = 'component_bundle_configurations' 
              AND tbc.activation_status = 'Completed'
        """, {
            "operations": list(all_operations),
            "cells": cells,
            "work_order": wo_name
        }, as_dict=True)

    from collections import defaultdict
    cell_op_size_completed = defaultdict(int)
    cell_op_size_rejected = defaultdict(int)
    for log in scan_logs:
        key = (log.physical_cell, log.operation, log.size or "")
        if log.status in ('Counted', 'Activated', 'Pass'):
            cell_op_size_completed[key] += log.pi_qty or 0
        elif log.status in ('QC Reject','SP Reject'):  # NEW
            cell_op_size_rejected[key] += log.pi_qty or 0   

    metrics_by_cell = []
    for cell in cells:
        first_op = cell_first_last[cell]["first"]
        last_op = cell_first_last[cell]["last"]
        for size in sizes:
            total_qty = size_qty_map[size]
            completed_first = cell_op_size_completed.get((cell, first_op, size), 0)
            completed_last = cell_op_size_completed.get((cell, last_op, size), 0)
            wip = max(0, completed_first - completed_last)
            completed = completed_last
            rejected = cell_op_size_rejected.get((cell, last_op, size), 0)
            pending = max(total_qty - completed, 0)
            completion_pct = min((completed / total_qty) * 100, 100.0) if total_qty > 0 else 0.0

            metrics_by_cell.append({
                "physical_cell": cell,
                "size": size,
                "size_qty": total_qty,
                "completed_units": completed,
                "rejected_units": rejected,
                "pending_units": pending,
                "completion_pct": round(completion_pct, 1),
                "wip": wip
            })

    metrics_by_cell.sort(key=lambda x: (x["physical_cell"], x["size"]))
    return {
        "details": wo_details[0],
        "metrics_by_cell": metrics_by_cell
    }