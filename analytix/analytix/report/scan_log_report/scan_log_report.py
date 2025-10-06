# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": _("Logged Time"), "fieldname": "logged_time", "fieldtype": "Datetime", "width": 180},
        {"label": _("Scan Time"), "fieldname": "scan_time", "fieldtype": "Datetime", "width": 180},
        {"label": _("Ex Factory Date"), "fieldname": "ex_fty_date", "fieldtype": "Date", "width": 120},
        {"label": _("User"), "fieldname": "user", "fieldtype": "Data", "width": 150},
        {"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 120},
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 150},
        {"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 150},
        {"label": _("Line Item No"), "fieldname": "line_item_no", "fieldtype": "Data", "width": 120},
        {"label": _("Tracking Order"), "fieldname": "tracking_order", "fieldtype": "Link", "options": "Tracking Order", "width": 150},
        {"label": _("FG Item"), "fieldname": "fg_item", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Physical Cell"), "fieldname": "physical_cell", "fieldtype": "Data", "width": 120},
        {"label": _("Operation Type"), "fieldname": "operation_type", "fieldtype": "Data", "width": 130},
        {"label": _("Operation Group"), "fieldname": "operation_group", "fieldtype": "Data", "width": 140},
        {"label": _("Operation"), "fieldname": "operation", "fieldtype": "Link", "options": "Operation", "width": 130},
        {"label": _("Workstation"), "fieldname": "workstation", "fieldtype": "Link", "options": "Workstation", "width": 130},
        {"label": _("Component"), "fieldname": "component", "fieldtype": "Data", "width": 120},
        {"label": _("Size"), "fieldname": "size", "fieldtype": "Data", "width": 80},
        {"label": _("Style"), "fieldname": "style", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Colour"), "fieldname": "colour", "fieldtype": "Data", "width": 100},
        {"label": _("Material Composition"), "fieldname": "material_composition", "fieldtype": "Data", "width": 160},
        {"label": _("Production Item Number"), "fieldname": "production_item_number", "fieldtype": "Data", "width": 160},
        {"label": _("Tag Number"), "fieldname": "tag_number", "fieldtype": "Data", "width": 120},
        {"label": _("Sales Order Qty"), "fieldname": "sales_order_qty", "fieldtype": "Float", "width": 120},
        {"label": _("Sales Order Size Qty"), "fieldname": "sales_order_size_qty", "fieldtype": "Float", "width": 150},
        {"label": _("Work Order Qty"), "fieldname": "work_order_qty", "fieldtype": "Float", "width": 120},
        {"label": _("Work Order Size Qty"), "fieldname": "work_order_size_qty", "fieldtype": "Float", "width": 150},
        {"label": _("Bundle Quantity"), "fieldname": "bundle_quantity", "fieldtype": "Float", "width": 130},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Defect Code"), "fieldname": "defect_code", "fieldtype": "Data", "width": 120},
        {"label": _("Defect"), "fieldname": "defect", "fieldtype": "Data", "width": 120},
        {"label": _("Defect Description"), "fieldname": "defect_description", "fieldtype": "Text", "width": 200},
        {"label": _("Defect Severity"), "fieldname": "defect_severity", "fieldtype": "Data", "width": 120},
    ]

def get_data(filters):
    conditions = [
        "isl.log_status = 'Completed'",
        "tbc.parentfield = 'component_bundle_configurations'",
        "tbc.bc_name LIKE '%%-A'" # Temporary Condition. Need to check with Hassan about ths column and modify
    ]

    # Date Range Filter
    if filters.get("from_date"):
        conditions.append("DATE(isl.logged_time) >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("DATE(isl.logged_time) <= %(to_date)s")

    # Sales Order Filter
    if filters.get("sales_order"):
        conditions.append("tbc.sales_order = %(sales_order)s")

    # Work Order Filter
    if filters.get("work_order"):
        conditions.append("tbc.work_order = %(work_order)s")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            DATE(isl.logged_time) AS `date`,
            isl.logged_time AS `logged_time`,
            isl.scan_time AS `scan_time`,
            DATE(soi.custom_ex_fty_date) AS `ex_fty_date`,
            isl.owner AS `user`,
            itm.brand AS `brand`,   
            tbc.sales_order AS `sales_order`,
            tbc.work_order AS `work_order`,
            woli.line_item_no AS `line_item_no`,
            tor.name AS `tracking_order`,
            tor.item AS `fg_item`,
            isl.physical_cell AS `physical_cell`,
            op.custom_operation_type AS `operation_type`,
            op.custom_operation_group AS `operation_group`,
            isl.operation AS `operation`,
            isl.workstation AS `workstation`,
            tc.component_name AS `component`,
            pi.size AS `size`, 
            itm.name AS `style`,
            itm.custom_colour_name AS `colour`,
            itm.custom_material_composition AS `material_composition`,
            pi.production_item_number AS `production_item_number`,
            tt.tag_number AS `tag_number`,
            so.total_qty AS `sales_order_qty`,
            soi.qty AS `sales_order_size_qty`,
            wo.qty AS `work_order_qty`,
            woli.work_order_allocated_qty AS `work_order_size_qty`,
            pi.quantity AS `bundle_quantity`,
            isl.status AS `status`,
            isld.defect_code AS `defect_code`,
            isld.defect AS `defect`,
            isld.defect_description AS `defect_description`,
            isld.severity AS `defect_severity`
        FROM `tabItem Scan Log` isl 
        LEFT JOIN `tabProduction Item` pi ON isl.production_item = pi.name
        LEFT JOIN `tabItem Scan Log Defect` isld ON isl.name = isld.parent
        LEFT JOIN `tabOperation` op ON isl.operation = op.name
        LEFT JOIN `tabTracking Component` tc ON pi.component = tc.name
        LEFT JOIN `tabTracking Order` tor ON tc.parent = tor.name
        LEFT JOIN `tabTracking Tag` tt ON pi.tracking_tag = tt.name 
        LEFT JOIN `tabTracking Order Bundle Configuration` tbc 
            ON tor.name = tbc.parent 
            AND pi.size = tbc.size 
            AND tc.name = tbc.component
        LEFT JOIN `tabItem` itm ON tor.item = itm.name
        LEFT JOIN `tabSales Order` so ON tbc.sales_order = so.name
        LEFT JOIN `tabSales Order Item` soi 
            ON so.name = soi.parent 
            AND tor.item = soi.item_code 
            AND pi.size = soi.custom_size
        LEFT JOIN `tabWork Order` wo ON tbc.work_order = wo.name
        LEFT JOIN `tabWork Order Line Item` woli 
            ON wo.name = woli.parent 
            AND so.name = woli.sales_order 
            AND pi.size = woli.size
        WHERE {where_clause}
        ORDER BY isl.logged_time DESC
    """

    data = frappe.db.sql(query, filters, as_dict=1)
    return data