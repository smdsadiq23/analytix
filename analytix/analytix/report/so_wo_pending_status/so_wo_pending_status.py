# Copyright (c) 2025, Your Company
# License: See license.txt

import frappe

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
    conds = [
		"so.docstatus = 1",
		"itm.custom_select_master = 'Finished Goods'",
		"tbc.parentfield = 'component_bundle_configurations'"
	]
    params = {}

    if filters.get("date_range"):
        start, end = filters["date_range"]
        conds.append("date(soi.custom_ex_fty_date) BETWEEN %(start)s AND %(end)s")
        params.update({"start": start, "end": end})

    if filters.get("operation"):
        conds.append("isl.operation = %(op)s")
        params["op"] = filters["operation"]

    where_clause = " AND ".join(conds)

    data = frappe.db.sql(f"""
        SELECT 
            so.name AS so_number,
            so.total_qty AS so_quantity,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('Counted','Activated','Pass') 
                THEN pi.quantity ELSE 0 END), 0) AS completed_units,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('QC Rework','QC Reject','QC Recut','SP Rework','SP Recut','SP Reject') 
                THEN pi.quantity ELSE 0 END), 0) AS rejected_units
        FROM `tabSales Order` so
        INNER JOIN (
            SELECT parent, custom_ex_fty_date, item_code
            FROM `tabSales Order Item`
            WHERE custom_ex_fty_date IS NOT NULL
            GROUP BY parent, custom_ex_fty_date, item_code
        ) soi ON soi.parent = so.name
        INNER JOIN `tabItem` itm ON itm.name = soi.item_code
        LEFT JOIN `tabTracking Order Bundle Configuration` tbc ON tbc.sales_order = so.name
        LEFT JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        LEFT JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
        LEFT JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        LEFT JOIN `tabItem Scan Log` isl ON isl.production_item = pi.name AND isl.log_status = 'Completed'
        WHERE {where_clause}
        GROUP BY so.name, so.total_qty
        HAVING so_quantity > 0
    """, params, as_dict=True)

    for row in data:
        row.pending_units = row.so_quantity - (row.completed_units or 0) - (row.rejected_units or 0)
    return data


def get_summary_wo(filters):
    conds = [
		"wo.docstatus = 1",
		"itm.custom_select_master = 'Finished Goods'",
		"tbc.parentfield = 'component_bundle_configurations'"
	]
    params = {}

    if filters.get("date_range"):
        start, end = filters["date_range"]
        conds.append("date(soi.custom_ex_fty_date) BETWEEN %(start)s AND %(end)s")
        params.update({"start": start, "end": end})

    if filters.get("operation"):
        conds.append("isl.operation = %(op)s")
        params["op"] = filters["operation"]

    where_clause = " AND ".join(conds)

    data = frappe.db.sql(f"""
        SELECT 
            wo.name AS wo_number,
            wo.qty AS wo_quantity,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('Counted','Activated','Pass') 
                THEN pi.quantity ELSE 0 END), 0) AS completed_units,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('QC Rework','QC Reject','QC Recut','SP Rework','SP Recut','SP Reject') 
                THEN pi.quantity ELSE 0 END), 0) AS rejected_units
        FROM `tabWork Order` wo
        INNER JOIN (
            SELECT parent AS work_order, sales_order
            FROM `tabWork Order Sales Orders`
            WHERE sales_order IS NOT NULL
            GROUP BY parent
        ) woso ON woso.work_order = wo.name
        INNER JOIN (
            SELECT parent, custom_ex_fty_date, item_code
            FROM `tabSales Order Item`
            WHERE custom_ex_fty_date IS NOT NULL
            GROUP BY parent, custom_ex_fty_date, item_code
        ) soi ON soi.parent = woso.sales_order AND soi.item_code = wo.production_item
        INNER JOIN `tabItem` itm ON itm.name = wo.production_item AND itm.custom_select_master = 'Finished Goods'
        LEFT JOIN `tabTracking Order Bundle Configuration` tbc ON tbc.work_order = wo.name
        LEFT JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        LEFT JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
        LEFT JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        LEFT JOIN `tabItem Scan Log` isl ON isl.production_item = pi.name AND isl.log_status = 'Completed'
        WHERE {where_clause}
        GROUP BY wo.name, wo.qty
        HAVING wo_quantity > 0
    """, params, as_dict=True)

    for row in data:
        row.pending_units = row.wo_quantity - (row.completed_units or 0) - (row.rejected_units or 0)
    return data


def get_detail_so(so_name):
    if not so_name:
        return {}

    conds = ["so.name = %(so_name)s", "so.docstatus = 1"]
    params = {"so_name": so_name}

    # Get SO details
    so_details = frappe.db.sql(f"""
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
        WHERE { ' AND '.join(conds) }
        GROUP BY so.name, so.total_qty
    """, params, as_dict=True)

    if not so_details:
        frappe.msgprint("No Sales Order details found or not an FG Item")
        return {} 
    
	# Get metrics by operation and size
    metrics_by_op = frappe.db.sql(f"""
        SELECT 
            isl.operation,
            soi.custom_size AS size,
            SUM(soi.qty) AS size_qty,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('Counted','Activated','Pass') 
                THEN pi.quantity ELSE 0 END), 0) AS completed_units,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('QC Rework','QC Reject','QC Recut','SP Rework','SP Recut','SP Reject') 
                THEN pi.quantity ELSE 0 END), 0) AS rejected_units
        FROM `tabSales Order` so
        INNER JOIN (
            SELECT parent, item_code, custom_ex_fty_date, custom_size, qty
            FROM `tabSales Order Item`
            GROUP BY parent, item_code, custom_ex_fty_date, custom_size
        ) soi ON soi.parent = so.name
		INNER JOIN `tabItem` itm ON itm.name = soi.item_code AND itm.custom_select_master = 'Finished Goods'
        LEFT JOIN `tabTracking Order Bundle Configuration` tbc ON tbc.sales_order = so.name AND tbc.size = soi.custom_size
        LEFT JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        LEFT JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
        LEFT JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        LEFT JOIN `tabItem Scan Log` isl ON isl.production_item = pi.name AND isl.log_status = 'Completed'
        WHERE tbc.parentfield = 'component_bundle_configurations' AND {' AND '.join(conds)}
        GROUP BY isl.operation, soi.custom_size
        ORDER BY isl.operation, soi.custom_size
    """, params, as_dict=True)

    for row in metrics_by_op:
        row.pending_units = row.size_qty - (row.completed_units or 0) - (row.rejected_units or 0)
        
    if not metrics_by_op:
        frappe.msgprint("No operation metrics found")

    return {
        "details": so_details[0],
        "metrics_by_op": metrics_by_op
    }


def get_detail_wo(wo_name):
    if not wo_name:
        return {}

    conds = ["wo.name = %(wo_name)s", "wo.docstatus = 1"]
    params = {"wo_name": wo_name}

    # Get WO details
    wo_details = frappe.db.sql(f"""
        SELECT 
            wo.name AS wo_number,
            wo.qty AS wo_quantity,
            date(soi.custom_ex_fty_date) AS ex_factory_date,
            itm.brand AS fty_client,
            itm.item_name AS product_family,
            itm.name AS fty_prod_id,
            itm.name AS style,
            itm.custom_colour_code AS color,
            itm.custom_material_composition AS material
        FROM `tabWork Order` wo
        INNER JOIN (
            SELECT parent AS work_order, sales_order
            FROM `tabWork Order Sales Orders`
            GROUP BY parent
        ) woso ON woso.work_order = wo.name
        INNER JOIN (
            SELECT parent, custom_ex_fty_date, item_code
            FROM `tabSales Order Item`
            GROUP BY parent, custom_ex_fty_date, item_code
        ) soi ON soi.parent = woso.sales_order AND soi.item_code = wo.production_item
        INNER JOIN `tabItem` itm ON itm.name = wo.production_item AND itm.custom_select_master = 'Finished Goods'
        WHERE {' AND '.join(conds)}
        LIMIT 1
    """, params, as_dict=True)

    if not wo_details:
        frappe.msgprint("No Work Order details found or not an FG Item")
        return {}

    # Get metrics by operation and size
    metrics_by_op = frappe.db.sql(f"""
        SELECT 
            isl.operation,
            woli.size,
            SUM(woli.qty) AS size_qty,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('Counted','Activated','Pass') 
                THEN pi.quantity ELSE 0 END), 0) AS completed_units,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('QC Rework','QC Reject','QC Recut','SP Rework','SP Recut','SP Reject') 
                THEN pi.quantity ELSE 0 END), 0) AS rejected_units
        FROM `tabWork Order` wo
        INNER JOIN (
            SELECT parent, size, work_order_allocated_qty AS qty
            FROM `tabWork Order Line Item`
            GROUP BY parent, size
        ) woli ON woli.parent = wo.name
        LEFT JOIN (
            SELECT parent AS work_order, sales_order
            FROM `tabWork Order Sales Orders`
            WHERE sales_order IS NOT NULL
            GROUP BY parent
        ) woso ON woso.work_order = wo.name
        LEFT JOIN (
            SELECT parent, custom_ex_fty_date
            FROM `tabSales Order Item`
            GROUP BY parent	
        ) soi ON soi.parent = woso.sales_order
        INNER JOIN `tabItem` itm ON itm.name = wo.production_item AND itm.custom_select_master = 'Finished Goods'
        LEFT JOIN `tabTracking Order Bundle Configuration` tbc ON tbc.work_order = wo.name AND tbc.size = woli.size
        LEFT JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        LEFT JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name AND pi.bundle_configuration = tbc.name
        LEFT JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        LEFT JOIN `tabItem Scan Log` isl ON isl.production_item = pi.name AND isl.log_status = 'Completed'
        WHERE tbc.parentfield = 'component_bundle_configurations' AND {' AND '.join(conds)}
        GROUP BY isl.operation, woli.size
        ORDER BY isl.operation, woli.size
    """, params, as_dict=True)

    for row in metrics_by_op:
        row.pending_units = row.size_qty - (row.completed_units or 0) - (row.rejected_units or 0)
        
    if not metrics_by_op:
        frappe.msgprint("No operation metrics found for WO")        

    return {
        "details": wo_details[0],
        "metrics_by_op": metrics_by_op
    }
