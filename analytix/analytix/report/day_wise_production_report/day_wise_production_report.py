# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": "Process Date", "fieldname": "process_date", "fieldtype": "Date", "width": 110},
        {"label": "Department", "fieldname": "department", "fieldtype": "Data", "width": 150},
        {"label": "Buyer", "fieldname": "buyer", "fieldtype": "Data", "width": 150},
        {"label": "Season", "fieldname": "season", "fieldtype": "Data", "width": 100},
        {"label": "Style", "fieldname": "style", "fieldtype": "Data", "width": 130},
        {"label": "Colour", "fieldname": "colour", "fieldtype": "Data", "width": 100},
        {"label": "Size", "fieldname": "size", "fieldtype": "Data", "width": 80},
        {"label": "Order Qty", "fieldname": "order_qty", "fieldtype": "Int", "width": 110},
        {"label": "Completed Qty", "fieldname": "completed_qty", "fieldtype": "Int", "width": 120},
        {"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Int", "width": 120},
        {"label": "Completed %", "fieldname": "completed_percent", "fieldtype": "Percent", "width": 120}
    ]


def get_order_map(filters):
    """
    Fetches static order details mapped by (style, colour, size) combination.
    """
    conditions = []
    if filters.get("buyer"):
        conditions.append("so.customer_name = %(buyer)s")
    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            itm.custom_style_master AS style,
            itm.custom_colour_name AS colour,
            tbc.size AS size,
            so.customer_name AS buyer,
            stm.custom_season AS season,
            COALESCE(SUM(soi.custom_order_qty), 0) AS order_qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabSales Order` so ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabItem` itm ON itm.name = tor.item
        INNER JOIN `tabStyle Master` stm ON stm.name = itm.custom_style_master
        WHERE {where_clause}
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, 
                 so.customer_name, stm.custom_season
    """
    
    data = frappe.db.sql(query, filters, as_dict=True)
    # Create dictionary keyed by (style, colour, size)
    return {(row.style, row.colour, row.size): row for row in data}


def get_production_data(filters):
    """
    Fetches aggregated production data grouped by date, department, style, colour, size.
    """
    conditions = []
    if filters.get("date"):
        conditions.append("DATE(isl.logged_time) = %(date)s")
    if filters.get("department"):
        conditions.append("pc.cell_name = %(department)s")
    if filters.get("buyer"):
        conditions.append("so.customer_name = %(buyer)s")
    if filters.get("style"):
        conditions.append("itm.custom_style_master = %(style)s")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            DATE(isl.logged_time) AS process_date,
            pc.cell_name AS department,
            itm.custom_style_master AS style,
            itm.custom_colour_name AS colour,
            tbc.size AS size,
            COALESCE(SUM(pi.quantity), 0) AS completed_qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor ON tor.name = pi.tracking_order
        INNER JOIN `tabTracking Order Bundle Configuration` tbc ON tbc.parent = tor.name
        INNER JOIN `tabItem` itm ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo ON pcflo.parent = tbc.work_order
        INNER JOIN `tabSales Order` so ON so.name = tbc.sales_order
        WHERE isl.operation = pcflo.last_operation
            AND isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
            AND {where_clause}
        GROUP BY DATE(isl.logged_time), pc.cell_name, 
                 itm.custom_style_master, itm.custom_colour_name, tbc.size
        ORDER BY process_date DESC, pc.cell_name, itm.custom_style_master, tbc.size
    """
    
    return frappe.db.sql(query, filters, as_dict=True)


def get_data(filters):
    # Fetch Order Master Data
    order_map = get_order_map(filters)
    
    if not order_map:
        return []

    # Fetch Production Scan Data
    production_logs = get_production_data(filters)
    
    result = []
    
    # Merge and Calculate in Python
    for log in production_logs:
        key = (log.style, log.colour, log.size)
        
        # Skip if not in order map
        if key not in order_map:
            continue
            
        order_info = order_map[key]
        
        order_qty = int(order_info.order_qty)
        completed_qty = int(log.completed_qty)
        
        # Calculate Balance (Completed - Order)
        balance_qty = completed_qty - order_qty
        
        # Calculate Percentage
        if order_qty > 0:
            completed_percent = round((completed_qty / order_qty) * 100, 2)
        else:
            completed_percent = 0.0
            
        row = {
            "process_date": log.process_date,
            "department": log.department,
            "buyer": order_info.buyer,
            "season": order_info.season,
            "style": log.style,
            "colour": log.colour,
            "size": log.size,
            "order_qty": order_qty,
            "completed_qty": completed_qty,
            "balance_qty": balance_qty,
            "completed_percent": completed_percent
        }
        result.append(row)
    
    return result