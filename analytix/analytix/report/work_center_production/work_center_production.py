# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import date
from collections import defaultdict

def execute(filters=None):
    filters = frappe._dict(filters or {})

    as_on_date = frappe.utils.getdate(filters.as_on_date or date.today())
    unit = filters.get("unit")  # optional string

    # Step 1: Get active OCNs first (lightweight query - only OCNs with activity on selected date)
    active_ocns = get_active_ocns(as_on_date, unit)
    
    if not active_ocns:
        return get_columns(), [], f"No production activity found on {as_on_date.strftime('%d %b %Y')}."

    # Step 2: Fetch sales order info for active OCNs only (single query)
    order_info = get_sales_order_info(active_ocns)
    if not order_info:
        return get_columns(), [], "No matching Sales Orders found."

    # Step 3: Fetch production data only for active OCNs (filtered at DB level)
    cutting_rows = get_cutting_data(as_on_date, active_ocns, unit)
    sew_fin_rows = get_sewing_finishing_data(as_on_date, active_ocns, unit)

    # Step 4: Process and aggregate in Python
    data = process_production_data(
        order_info, 
        cutting_rows, 
        sew_fin_rows, 
        as_on_date
    )

    message = f"Production report for {as_on_date.strftime('%d %b %Y')} - showing all OCNs with activity"
    return get_columns(), data, message


def get_active_ocns(as_on_date, unit=None):
    """Lightweight query to get only OCNs with activity on the selected date"""
    conditions = ["DATE(creation) = %(as_on_date)s"]
    values = {"as_on_date": as_on_date}
    
    if unit:
        conditions.append("factory_business_unit = %(unit)s")
        values["unit"] = unit
    
    where_clause = " AND ".join(conditions)
    
    # Get OCNs from cutting
    cutting_query = f"""
        SELECT DISTINCT cci.sales_order AS ocn
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` con ON con.name = cci.parent
        WHERE con.docstatus = 1 AND {where_clause.replace('creation', 'con.creation')}
    """
    
    # Get OCNs from sewing/finishing
    sewing_query = f"""
        SELECT DISTINCT tbc.sales_order AS ocn
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi ON pi.name = isl.production_item
        INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabTracking Order Bundle Configuration` tbc ON tbc.name = pi.bundle_configuration
        INNER JOIN `tabCut Kit Plan Bundle Details` ckd ON ckd.production_item_id = pi.name
        INNER JOIN `tabCut Kit Plan` ckp ON ckp.name = ckd.parent
        WHERE isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
            AND (isl.operation = 'Endline QC' OR isl.operation LIKE 'Finishing QC%%')
            AND {where_clause.replace('creation', 'isl.creation').replace('factory_business_unit', 'ckp.factory_business_unit')}
    """
    
    cutting_ocns = frappe.db.sql(cutting_query, values, as_dict=True)
    sewing_ocns = frappe.db.sql(sewing_query, values, as_dict=True)
    
    # Combine and return unique OCNs
    ocns = set()
    for row in cutting_ocns:
        ocns.add(row.ocn)
    for row in sewing_ocns:
        ocns.add(row.ocn)
    
    return list(ocns)


def get_sales_order_info(ocn_list):
    """Fetch style and order qty for given OCN(s) - single query"""
    if not ocn_list:
        return {}
    
    query = """
        SELECT 
            so.name AS ocn,
            soi.custom_style AS style,
            SUM(soi.qty) AS order_qty
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        WHERE so.name IN %(ocn_list)s
        GROUP BY so.name, soi.custom_style
    """
    rows = frappe.db.sql(query, {"ocn_list": ocn_list}, as_dict=True)
    
    result = {}
    for r in rows:
        if r.ocn not in result:
            result[r.ocn] = {}
        result[r.ocn][r.style] = r.order_qty
    return result


def get_cutting_data(to_date, ocn_list, unit=None):
    """Fetch cutting data only for active OCNs - no GROUP BY, aggregate in Python"""
    if not ocn_list:
        return []
    
    conditions = [
        "cci.docstatus = 1",
        "con.docstatus = 1",
        "cci.sales_order IN %(ocn_list)s",
        "DATE(con.creation) <= %(to_date)s"
    ]
    values = {
        "to_date": to_date,
        "ocn_list": ocn_list
    }

    if unit:
        conditions.append("fbu.name = %(unit)s")
        values["unit"] = unit

    where_clause = " AND ".join(conditions)

    # Removed GROUP BY - let Python handle aggregation
    query = f"""
        SELECT
            cci.sales_order AS ocn,
            cd.style_no AS style,
            fbu.factory_name,
            cci.confirmed_quantity AS cut_quantity,
            DATE(con.creation) AS scan_date
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` con 
            ON con.name = cci.parent
        INNER JOIN `tabCut Docket` cd
            ON cd.name = con.cut_po_number
        LEFT JOIN `tabFactory Business Unit` fbu 
            ON fbu.name = con.factory_business_unit
        WHERE {where_clause}
    """
    return frappe.db.sql(query, values, as_dict=True)


def get_sewing_finishing_data(to_date, ocn_list, unit=None):
    """Fetch sewing/finishing data only for active OCNs - no GROUP BY, aggregate in Python"""
    if not ocn_list:
        return []
    
    conditions = [
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Activated', 'Pass')",
        "tbc.sales_order IN %(ocn_list)s",
        "DATE(isl.creation) <= %(to_date)s",
        "(isl.operation = 'Endline QC' OR isl.operation LIKE 'Finishing QC%%')"
    ]
    values = {
        "to_date": to_date,
        "ocn_list": ocn_list
    }

    if unit:
        conditions.append("fbu.name = %(unit)s")
        values["unit"] = unit

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT 
            tbc.sales_order AS ocn,
            ckp.style AS style,
            fbu.factory_name,
            pi.quantity,
            DATE(isl.creation) AS scan_date,
            isl.operation
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi 
            ON pi.name = isl.production_item
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
            ON tbc.name = pi.bundle_configuration
        INNER JOIN `tabCut Kit Plan Bundle Details` ckd 
            ON ckd.production_item_id = pi.name
        INNER JOIN `tabCut Kit Plan` ckp 
            ON ckp.name = ckd.parent
        LEFT JOIN `tabFactory Business Unit` fbu 
            ON fbu.name = ckp.factory_business_unit
        WHERE {where_clause}
    """
    return frappe.db.sql(query, values, as_dict=True)


def process_production_data(order_info, cutting_rows, sew_fin_rows, as_on_date):
    """Aggregate all production data in Python - single pass through data"""
    
    # Initialize summary structure
    summary = {}
    for ocn_key, styles in order_info.items():
        for style, qty in styles.items():
            key = (ocn_key, style)
            summary[key] = {
                "unit": "-",
                "ocn": ocn_key,
                "style": style,
                "order_quantity": qty,
                "cutting_on_date": 0,
                "cutting_till_date": 0,
                "sewing_on_date": 0,
                "sewing_till_date": 0,
                "finishing_on_date": 0,
                "finishing_till_date": 0
            }
    
    # Process cutting data - single pass
    for row in cutting_rows:
        key = (row.ocn, row.style)
        if key not in summary:
            continue
            
        summary[key]["unit"] = row.factory_name or "-"
        summary[key]["cutting_till_date"] += row.cut_quantity
        
        if row.scan_date == as_on_date:
            summary[key]["cutting_on_date"] += row.cut_quantity
    
    # Process sewing & finishing data - single pass
    for row in sew_fin_rows:
        key = (row.ocn, row.style)
        if key not in summary:
            continue
            
        summary[key]["unit"] = row.factory_name or "-"
        
        # Determine operation type
        if row.operation == "Endline QC":
            summary[key]["sewing_till_date"] += row.quantity
            if row.scan_date == as_on_date:
                summary[key]["sewing_on_date"] += row.quantity
                
        elif row.operation.startswith("Finishing QC"):
            summary[key]["finishing_till_date"] += row.quantity
            if row.scan_date == as_on_date:
                summary[key]["finishing_on_date"] += row.quantity
    
    # Convert to list and sort
    data = list(summary.values())
    data.sort(key=lambda x: (x["unit"], x["ocn"], x["style"]))
    
    return data


def get_columns():
    return [
        {"label": "Unit", "fieldname": "unit", "fieldtype": "Data", "width": 120},
        {"label": "OCN", "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 140},
        {"label": "Style", "fieldname": "style", "fieldtype": "Data", "width": 160},
        {"label": "Order Quantity", "fieldname": "order_quantity", "fieldtype": "Int", "width": 140},
        {"label": "Cutting - On Date", "fieldname": "cutting_on_date", "fieldtype": "Int", "width": 150},
        {"label": "Cutting - Till Date", "fieldname": "cutting_till_date", "fieldtype": "Int", "width": 150},
        {"label": "Sewing - On Date", "fieldname": "sewing_on_date", "fieldtype": "Int", "width": 150},
        {"label": "Sewing - Till Date", "fieldname": "sewing_till_date", "fieldtype": "Int", "width": 150},
        {"label": "Finishing - On Date", "fieldname": "finishing_on_date", "fieldtype": "Int", "width": 160},
        {"label": "Finishing - Till Date", "fieldname": "finishing_till_date", "fieldtype": "Int", "width": 160},
    ]