# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime


def execute(filters=None):
    filters = filters or {}
    summary_so = get_summary_so(filters)
    summary_wo = get_summary_wo(filters)
    detail_so = get_detail_so(filters.get("sales_order"))
    detail_wo = get_detail_wo(filters.get("work_order"))

    return [], [], None, None, [
        {"name": "summary_so", "data": summary_so or []},
        {"name": "summary_wo", "data": summary_wo or []},
        {"name": "detail_so", "data": detail_so or {}},
        {"name": "detail_wo", "data": detail_wo or {}}
    ]


def get_summary_so(filters):
    """Per-Sales Order summary for a selected operation."""
    if not filters.get("operation"):
        return []

    params = {"op": filters["operation"]}
    if filters.get("date_range"):
        start, end = filters["date_range"]
        params.update({"start": start, "end": end})
        date_pred = "DATE(soi.custom_ex_fty_date) BETWEEN %(start)s AND %(end)s"
    else:
        params["year"] = now_datetime().year
        date_pred = "YEAR(soi.custom_ex_fty_date) = %(year)s"

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
              AND {date_pred}
        ) soi_ok ON soi_ok.parent = so.name
        LEFT JOIN (
            SELECT 
                tbc.sales_order,
                SUM(CASE 
                    WHEN isl.log_status = 'Completed'
                     AND isl.status IN ('Counted','Activated','Pass')
                    THEN pi.quantity ELSE 0 
                END) AS completed_units,
                COUNT(CASE 
                    WHEN isl.log_status = 'Completed'
                     AND isl.status IN ('QC Reject','QC Recut','SP Recut','SP Reject')
                    THEN 1
                END) AS rejected_units
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
            INNER JOIN `tabOperation Map` opm ON opm.parent = tor.name AND opm.operation = %(op)s
            INNER JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl ON isl.production_item = pi.name AND isl.operation = opm.operation
            WHERE tbc.parentfield = 'component_bundle_configurations' AND tbc.activation_status = 'Completed' AND tbc.sales_order IS NOT NULL
            GROUP BY tbc.sales_order
        ) sa ON sa.sales_order = so.name
        WHERE so.docstatus = 1
        HAVING so_quantity > 0
        ORDER BY so.name
        """,
        params,
        as_dict=True,
    )


def get_summary_wo(filters):
    """Per-Work Order summary for a selected operation."""
    if not filters.get("operation"):
        return []

    params = {"op": filters["operation"]}
    if filters.get("date_range"):
        start, end = filters["date_range"]
        params.update({"start": start, "end": end})
        date_pred = "DATE(soi.custom_ex_fty_date) BETWEEN %(start)s AND %(end)s"
    else:
        params["year"] = now_datetime().year
        date_pred = "YEAR(soi.custom_ex_fty_date) = %(year)s"

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
              AND {date_pred}
        ) soi_ok ON soi_ok.sales_order = woso.sales_order AND soi_ok.item_code = wo.production_item
        LEFT JOIN (
            SELECT 
                tbc.work_order,
                SUM(CASE 
                    WHEN isl.log_status = 'Completed'
                     AND isl.status IN ('Counted','Activated','Pass')
                    THEN pi.quantity ELSE 0 
                END) AS completed_units,
                COUNT(CASE 
                    WHEN isl.log_status = 'Completed'
                     AND isl.status IN ('QC Reject','QC Recut','SP Recut','SP Reject')
                    THEN 1
                END) AS rejected_units
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
            INNER JOIN `tabOperation Map` opm ON opm.parent = tor.name AND opm.operation = %(op)s
            INNER JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl ON isl.production_item = pi.name AND isl.operation = opm.operation
            WHERE tbc.parentfield = 'component_bundle_configurations' AND tbc.activation_status = 'Completed' AND tbc.work_order IS NOT NULL
            GROUP BY tbc.work_order
        ) sa ON sa.work_order = wo.name
        WHERE wo.docstatus = 1
        HAVING wo_quantity > 0
        ORDER BY wo.name
        """,
        params,
        as_dict=True,
    )


def get_detail_so(so_name):
    if not so_name:
        return {}

    # Fetch SO header details
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
        WHERE so.name = %s AND so.docstatus = 1
        GROUP BY so.name, so.total_qty
    """, (so_name,), as_dict=True)

    if not so_details:
        return {}

    # Get size-wise quantities
    size_qty_list = frappe.db.sql("""
        SELECT custom_size, SUM(qty) AS qty
        FROM `tabSales Order Item`
        WHERE parent = %s
        GROUP BY custom_size
    """, (so_name,), as_dict=True)
    size_qty_map = {row.custom_size or "": row.qty for row in size_qty_list}
    sizes = list(size_qty_map.keys())

    if not sizes:
        return {"details": so_details[0], "metrics_by_op": []}

    # Get operation links to build sequence and previous map
    op_links = frappe.db.sql("""
        SELECT DISTINCT opm.operation, opm.next_operation
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabOperation Map` opm ON opm.parent = tor.name
        WHERE tbc.sales_order = %s AND tbc.parentfield = 'component_bundle_configurations' AND tbc.activation_status = 'Completed'
    """, (so_name,), as_dict=True)

    # Build next_to_prev map and collect all operations
    next_to_prev = {}
    all_ops_set = set()
    op_to_next = {}
    for row in op_links:
        op = row.operation
        nxt = row.next_operation
        all_ops_set.add(op)
        if nxt:
            all_ops_set.add(nxt)
            next_to_prev[nxt] = op
        op_to_next[op] = nxt

    if not all_ops_set:
        return {"details": so_details[0], "metrics_by_op": []}

    # Build operation sequence (handle multiple chains if needed)
    next_ops = set(op_to_next.values())
    first_ops = [op for op in all_ops_set if op not in next_ops]
    
    operation_sequence = []
    for start in first_ops:
        current = start
        while current:
            operation_sequence.append(current)
            current = op_to_next.get(current)
    
    # Remove duplicates while preserving order
    seen = set()
    ordered_ops = []
    for op in operation_sequence:
        if op not in seen:
            ordered_ops.append(op)
            seen.add(op)
    
    # Create sort order map
    sort_order_map = {op: idx for idx, op in enumerate(ordered_ops)}

    # Fetch latest scan per (Production Item, Operation) — deduplicated
    scan_logs = frappe.db.sql("""
        SELECT
            opm.operation,
            tbc.size,
            pi.quantity AS pi_qty,
            isl.status
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabOperation Map` opm ON opm.parent = tor.name
        INNER JOIN `tabProduction Item` pi 
            ON pi.tracking_order = tor.name 
            AND pi.bundle_configuration = tbc.name
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN (
            SELECT production_item, operation, MAX(creation) AS max_creation
            FROM `tabItem Scan Log`
            WHERE log_status = 'Completed'
              AND status IN ('Counted','Activated','Pass','QC Reject','QC Recut','SP Recut','SP Reject')
            GROUP BY production_item, operation
        ) latest_scan ON latest_scan.production_item = pi.name AND latest_scan.operation = opm.operation
        INNER JOIN `tabItem Scan Log` isl 
            ON isl.production_item = pi.name 
            AND isl.operation = opm.operation
            AND isl.creation = latest_scan.max_creation
        WHERE tbc.sales_order = %s
          AND tbc.parentfield = 'component_bundle_configurations' AND tbc.activation_status = 'Completed'
    """, (so_name,), as_dict=True)

    # Aggregate completed and rejected units per (operation, size)
    from collections import defaultdict
    op_size_data = defaultdict(lambda: {"completed": 0, "rejected": 0})

    for log in scan_logs:
        key = (log.operation, log.size or "")
        if log.status in ('Counted', 'Activated', 'Pass'):
            op_size_data[key]["completed"] += log.pi_qty or 0
        elif log.status in ('QC Reject', 'QC Recut', 'SP Recut', 'SP Reject'):
            op_size_data[key]["rejected"] += 1

    # Build final metrics with WIP and sort_order
    metrics_by_op = []
    for op in ordered_ops:  # iterate in correct sequence
        for size in sizes:
            key = (op, size)
            total_qty = size_qty_map[size]
            completed = op_size_data[key]["completed"]
            rejected = op_size_data[key]["rejected"]
            pending = max(total_qty - completed - rejected, 0)
            completion_pct = min((completed / total_qty) * 100, 100.0) if total_qty > 0 else 0.0

            # 🔑 Calculate WIP (backlog)
            prev_op = next_to_prev.get(op)
            if prev_op:
                prev_key = (prev_op, size)
                completed_prev = op_size_data[prev_key]["completed"]
                wip = max(0, completed_prev - completed)
            else:
                wip = 0  # First operation has no upstream

            metrics_by_op.append({
                "operation": op,
                "size": size,
                "size_qty": total_qty,
                "completed_units": completed,
                "rejected_units": rejected,
                "pending_units": pending,
                "completion_pct": round(completion_pct, 1),
                "wip": wip,
                "sort_order": sort_order_map[op]
            })

    # Sort by operation sequence then size
    metrics_by_op.sort(key=lambda x: (x["sort_order"], x["size"]))
    return {
        "details": so_details[0],
        "metrics_by_op": metrics_by_op
    }


def get_detail_wo(wo_name):
    if not wo_name:
        return {}

    # Fetch WO header details
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
        WHERE wo.name = %s AND wo.docstatus = 1
        GROUP BY wo.name, wo.qty
    """, (wo_name,), as_dict=True)

    if not wo_details:
        return {}

    # Get size-wise quantities
    size_qty_list = frappe.db.sql("""
        SELECT size, SUM(work_order_allocated_qty) AS qty
        FROM `tabWork Order Line Item`
        WHERE parent = %s
        GROUP BY size
    """, (wo_name,), as_dict=True)
    size_qty_map = {row.size or "": row.qty for row in size_qty_list}
    sizes = list(size_qty_map.keys())

    if not sizes:
        return {"details": wo_details[0], "metrics_by_op": []}

    # Get operation links to build sequence and previous map
    op_links = frappe.db.sql("""
        SELECT DISTINCT opm.operation, opm.next_operation
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabOperation Map` opm ON opm.parent = tor.name
        WHERE tbc.work_order = %s AND tbc.parentfield = 'component_bundle_configurations' AND tbc.activation_status = 'Completed'
    """, (wo_name,), as_dict=True)

    # Build next_to_prev map and collect all operations
    next_to_prev = {}
    all_ops_set = set()
    op_to_next = {}
    for row in op_links:
        op = row.operation
        nxt = row.next_operation
        all_ops_set.add(op)
        if nxt:
            all_ops_set.add(nxt)
            next_to_prev[nxt] = op
        op_to_next[op] = nxt

    if not all_ops_set:
        return {"details": wo_details[0], "metrics_by_op": []}

    # Build operation sequence (handle multiple chains if needed)
    next_ops = set(op_to_next.values())
    first_ops = [op for op in all_ops_set if op not in next_ops]
    
    operation_sequence = []
    for start in first_ops:
        current = start
        while current:
            operation_sequence.append(current)
            current = op_to_next.get(current)
    
    # Remove duplicates while preserving order
    seen = set()
    ordered_ops = []
    for op in operation_sequence:
        if op not in seen:
            ordered_ops.append(op)
            seen.add(op)
    
    # Create sort order map
    sort_order_map = {op: idx for idx, op in enumerate(ordered_ops)}

    # Fetch latest scan per (Production Item, Operation) — deduplicated
    scan_logs = frappe.db.sql("""
        SELECT
            opm.operation,
            tbc.size,
            pi.quantity AS pi_qty,
            isl.status
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabOperation Map` opm ON opm.parent = tor.name
        INNER JOIN `tabProduction Item` pi 
            ON pi.tracking_order = tor.name 
            AND pi.bundle_configuration = tbc.name
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN (
            SELECT production_item, operation, MAX(creation) AS max_creation
            FROM `tabItem Scan Log`
            WHERE log_status = 'Completed'
              AND status IN ('Counted','Activated','Pass','QC Reject','QC Recut','SP Recut','SP Reject')
            GROUP BY production_item, operation
        ) latest_scan ON latest_scan.production_item = pi.name AND latest_scan.operation = opm.operation
        INNER JOIN `tabItem Scan Log` isl 
            ON isl.production_item = pi.name 
            AND isl.operation = opm.operation
            AND isl.creation = latest_scan.max_creation
        WHERE tbc.work_order = %s
          AND tbc.parentfield = 'component_bundle_configurations' AND tbc.activation_status = 'Completed'
    """, (wo_name,), as_dict=True)

    # Aggregate completed and rejected units per (operation, size)
    from collections import defaultdict
    op_size_data = defaultdict(lambda: {"completed": 0, "rejected": 0})

    for log in scan_logs:
        key = (log.operation, log.size or "")
        if log.status in ('Counted', 'Activated', 'Pass'):
            op_size_data[key]["completed"] += log.pi_qty or 0
        elif log.status in ('QC Reject', 'QC Recut', 'SP Recut', 'SP Reject'):
            op_size_data[key]["rejected"] += 1

    # Build final metrics with WIP and sort_order
    metrics_by_op = []
    for op in ordered_ops:  # iterate in correct sequence
        for size in sizes:
            key = (op, size)
            total_qty = size_qty_map[size]
            completed = op_size_data[key]["completed"]
            rejected = op_size_data[key]["rejected"]
            pending = max(total_qty - completed - rejected, 0)
            completion_pct = min((completed / total_qty) * 100, 100.0) if total_qty > 0 else 0.0

            # 🔑 Calculate WIP (backlog)
            prev_op = next_to_prev.get(op)
            if prev_op:
                prev_key = (prev_op, size)
                completed_prev = op_size_data[prev_key]["completed"]
                wip = max(0, completed_prev - completed)
            else:
                wip = 0  # First operation has no upstream

            metrics_by_op.append({
                "operation": op,
                "size": size,
                "size_qty": total_qty,
                "completed_units": completed,
                "rejected_units": rejected,
                "pending_units": pending,
                "completion_pct": round(completion_pct, 1),
                "wip": wip,
                "sort_order": sort_order_map[op]
            })

    # Sort by operation sequence then size
    metrics_by_op.sort(key=lambda x: (x["sort_order"], x["size"]))
    return {
        "details": wo_details[0],
        "metrics_by_op": metrics_by_op
    }