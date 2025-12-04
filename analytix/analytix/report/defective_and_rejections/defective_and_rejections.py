# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    filters = filters or {}
    
    if not filters.get("date_range"):
        frappe.msgprint(_("Please select a Date Range"))
        return [], [], None, None, []

    defective_data = get_defective_data(filters)
    rejected_data = get_rejected_data(filters)

    return [], [], None, None, [
        {"name": "defective_table", "data": defective_data or []},
        {"name": "rejected_table", "data": rejected_data or []}
    ]


def get_conditions(filters, params):
    conds = []
    
    start, end = filters["date_range"]
    conds.append("DATE(isl.creation) BETWEEN %(start_date)s AND %(end_date)s")
    params.update({"start_date": start, "end_date": end})
    
    if filters.get("physical_cell"):
        conds.append("isl.physical_cell = %(physical_cell)s")
        params["physical_cell"] = filters["physical_cell"]
        
    if filters.get("operation"):
        conds.append("isl.operation = %(operation)s")
        params["operation"] = filters["operation"]
        
    if filters.get("workstation"):
        conds.append("isl.workstation = %(workstation)s")
        params["workstation"] = filters["workstation"]
        
    if filters.get("sales_order"):
        conds.append("tbc.sales_order = %(sales_order)s")
        params["sales_order"] = filters["sales_order"]
        
    if filters.get("work_order"):
        conds.append("tbc.work_order = %(work_order)s")
        params["work_order"] = filters["work_order"]
        
    return " AND ".join(conds)


def get_defective_data(filters):
    params = {}
    where_clause = get_conditions(filters, params)
    
    # Add style filter condition if present
    style_condition = ""
    if filters.get("style"):
        style_condition = "AND (soi.item_code = %(style)s OR woi.production_item = %(style)s)"
        params["style"] = filters["style"]
    
    data = frappe.db.sql(f"""
        SELECT
            DATE(isl.creation) AS date,
            isl.physical_cell,
            isl.operation,
            tbc.sales_order,
            tbc.work_order,
            COALESCE(soi.item_code, woi.production_item) AS fty_prod_id,
            COUNT(CASE 
                WHEN isl.status IN ('QC Rework','QC Reject','SP Rework','SP Reject') 
                THEN 1 END) AS defective_units,
            COUNT(*) AS scanned_units,
            ROUND(
                COUNT(CASE 
                    WHEN isl.status IN ('QC Rework','QC Reject','SP Rework','SP Reject') 
                    THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2
            ) AS defective_unit_percentage
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc 
            ON tbc.name = pi.bundle_configuration 
            AND tbc.parent = tor.name
        -- Join to Sales Order path
        LEFT JOIN `tabSales Order Item` soi 
            ON soi.parent = tbc.sales_order 
            AND soi.custom_size = tbc.size
        -- Join to Work Order path  
        LEFT JOIN `tabWork Order` woi 
            ON woi.name = tbc.work_order
        WHERE 
            isl.log_status = 'Completed'
            AND {where_clause}
            {style_condition}
        GROUP BY 
            DATE(isl.creation),
            isl.physical_cell,
            isl.operation,
            tbc.sales_order,
            tbc.work_order,
            COALESCE(soi.item_code, woi.production_item)
        ORDER BY DATE(isl.creation) DESC, defective_unit_percentage DESC
    """, params, as_dict=True)
    
    return data


def get_rejected_data(filters):
    params = {}
    where_clause = get_conditions(filters, params)
    
    style_condition = ""
    if filters.get("style"):
        style_condition = "AND (soi.item_code = %(style)s OR woi.production_item = %(style)s)"
        params["style"] = filters["style"]
    
    data = frappe.db.sql(f"""
        SELECT
            DATE(isl.creation) AS date,
            isl.physical_cell,
            isl.operation,
            tbc.sales_order,
            tbc.work_order,
            COALESCE(soi.item_code, woi.production_item) AS fty_prod_id,
            COUNT(CASE 
                WHEN isl.status IN ('QC Reject','SP Reject') 
                THEN 1 END) AS rejected_units,
            COUNT(*) AS scanned_units,
            ROUND(
                COUNT(CASE 
                    WHEN isl.status IN ('QC Reject','SP Reject') 
                    THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2
            ) AS rejected_unit_percentage
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc 
            ON tbc.name = pi.bundle_configuration 
            AND tbc.parent = tor.name
        LEFT JOIN `tabSales Order Item` soi 
            ON soi.parent = tbc.sales_order 
            AND soi.custom_size = tbc.size
        LEFT JOIN `tabWork Order` woi 
            ON woi.name = tbc.work_order
        WHERE 
            isl.log_status = 'Completed'
            AND {where_clause}
            {style_condition}
        GROUP BY 
            DATE(isl.creation),
            isl.physical_cell,
            isl.operation,
            tbc.sales_order,
            tbc.work_order,
            COALESCE(soi.item_code, woi.production_item)
        ORDER BY DATE(isl.creation) DESC, rejected_unit_percentage DESC
    """, params, as_dict=True)
    
    return data