# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from collections import defaultdict
from datetime import datetime

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    cols = [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": _("Week"), "fieldname": "week", "fieldtype": "Data", "width": 90},
        {"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 100},
        {"label": _("Buyer"), "fieldname": "buyer", "fieldtype": "Data", "width": 120},
        {"label": _("OCN"), "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 130},
        {"label": _("Style No"), "fieldname": "style_no", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": _("Colour"), "fieldname": "colour", "fieldtype": "Data", "width": 100},
    ]

    defect_list = get_defect_list()
    for defect in defect_list:
        fieldname = frappe.scrub(defect)[:60]
        cols.append({
            "label": _(defect),
            "fieldname": fieldname,
            "fieldtype": "Int",
            "width": 80
        })
    
    cols.append({
        "label": _("Total Defects"),
        "fieldname": "total_defects",
        "fieldtype": "Int",
        "width": 100
    })
    
    return cols

def get_defect_list():
    return frappe.db.get_all("Defect Master", filters={"name": ["is", "set"]}, pluck="name")

def get_data(filters):
    query = """
        SELECT
            DATE(isl.logged_time) AS date,
            itm.brand AS buyer,
            tbc.sales_order AS ocn,
            itm.name AS style_no,
            itm.custom_colour_name AS colour,
            isld.defect_description AS defect
        FROM `tabItem Scan Log` isl 
        LEFT JOIN `tabProduction Item` pi ON isl.production_item = pi.name
        LEFT JOIN `tabItem Scan Log Defect` isld ON isl.name = isld.parent
        LEFT JOIN `tabTracking Component` tc ON pi.component = tc.name
        LEFT JOIN `tabTracking Order` tor ON tc.parent = tor.name
        LEFT JOIN `tabTracking Tag` tt ON pi.tracking_tag = tt.name 
        LEFT JOIN `tabTracking Order Bundle Configuration` tbc 
            ON pi.bundle_configuration = tbc.name
        LEFT JOIN `tabItem` itm ON tor.item = itm.name
        LEFT JOIN `tabSales Order` so ON tbc.sales_order = so.name
        LEFT JOIN `tabSales Order Item` soi 
            ON so.name = soi.parent 
            AND tor.item = soi.item_code 
            AND pi.size = soi.custom_size
        WHERE 
            isl.log_status = 'Completed' 
            AND isl.Status LIKE '%Reject%' 
            AND tbc.parentfield = 'component_bundle_configurations' 
            # AND tbc.activation_status = 'Completed' 
            AND isld.defect_description IS NOT NULL
    """
    
    raw_data = frappe.db.sql(query, as_dict=1)
    all_defects = get_defect_list()
    defect_set = set(all_defects)
    
    grouped = defaultdict(lambda: defaultdict(int))
    totals = defaultdict(int)
    
    for row in raw_data:
        key = (row.date, row.buyer, row.ocn, row.style_no, row.colour)
        defect = row.defect
        
        if defect in defect_set:
            grouped[key][defect] += 1
            totals[key] += 1
    
    data = []
    for key, defect_counts in grouped.items():
        date, buyer, ocn, style_no, colour = key
        
        # === Add Week and Month ===
        if date:
            # Convert to datetime (date is already a date object in frappe.db.sql with as_dict=1)
            dt = datetime.combine(date, datetime.min.time())
            
            # Week: ISO format like "2024-W24"
            year, week, _ = dt.isocalendar()
            week_str = f"{year}-W{week:02d}"
            
            # Month: "Jun 2024"
            month_str = dt.strftime("%b %Y")  # Use "%B %Y" for full name (June 2024)
        else:
            week_str = ""
            month_str = ""
        
        row_dict = {
            "date": date,
            "week": week_str,
            "month": month_str,
            "buyer": buyer,
            "ocn": ocn,
            "style_no": style_no,
            "colour": colour,
        }
        
        for defect in all_defects:
            fieldname = frappe.scrub(defect)[:60]
            row_dict[fieldname] = defect_counts.get(defect, 0)
        
        row_dict["total_defects"] = totals[key]
        data.append(row_dict)
    
    return data