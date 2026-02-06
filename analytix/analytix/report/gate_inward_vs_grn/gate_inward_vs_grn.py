# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt



import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils.data import date_diff

def execute(filters=None):
    columns = get_columns()
    data = get_data()
    return columns, data, None, None, None, 0  # columns, data, message, chart, report_summary, skip_total_row

def get_columns():
    return [
        {"fieldname": "gate_entry_date", "label": _("Gate Entry Date"), "fieldtype": "Date", "width": 110},
        {"fieldname": "gate_inward_no", "label": _("Gate Inward No"), "fieldtype": "Link", "options": "Gate Inward Entry", "width": 180},
        {"fieldname": "party_dc_no", "label": _("Party DC No"), "fieldtype": "Data", "width": 120},
        {"fieldname": "party_dc_date", "label": _("Party DC Date"), "fieldtype": "Date", "width": 110},
        {"fieldname": "vehicle_no", "label": _("Vehicle No"), "fieldtype": "Data", "width": 120},
        {"fieldname": "party_name", "label": _("Party Name"), "fieldtype": "Data", "width": 180},
        {"fieldname": "department", "label": _("Department"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"fieldname": "delivery_qty", "label": _("Delivery Qty"), "fieldtype": "Int", "width": 100},
        {"fieldname": "inward_status", "label": _("Inward Status"), "fieldtype": "Data", "width": 100},
        {"fieldname": "uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM", "width": 80},
        {"fieldname": "remarks", "label": _("Remarks"), "fieldtype": "Small Text", "width": 200, "editable": 1},
        {"fieldname": "grn_created_on", "label": _("GRN Created On"), "fieldtype": "Date", "width": 110},
        {"fieldname": "unit_name", "label": _("Unit Name"), "fieldtype": "Data", "width": 130},
        {"fieldname": "user_id", "label": _("User Id/Name"), "fieldtype": "Data", "width": 150},
        {"fieldname": "age", "label": _("Age (Days)"), "fieldtype": "Int", "width": 90},
        {"fieldname": "purchase_receipt", "label": _("GRN No"), "fieldtype": "Link", "options": "Purchase Receipt", "width": 180, "hidden": 1}
    ]

def get_data():
    # Fetch all submitted Gate Inward Entries with linked Purchase Receipts (GRN)
    data = frappe.db.sql("""
        SELECT 
            DATE(gie.date_time) AS gate_entry_date,
            gie.name AS gate_inward_no,
            gie.dc_number AS party_dc_no,
            gie.dc_date AS party_dc_date,
            gie.vehicle_number AS vehicle_no,
            gie.party_name AS party_name,
            pr.set_warehouse AS department,
            gie.custom_qty AS delivery_qty,
            CASE 
                WHEN pr.docstatus = 1 THEN 'Completed'
                ELSE 'Pending'
            END AS inward_status,
            gie.custom_uom AS uom,
            pr.remarks AS remarks,
            pr.posting_date AS grn_created_on,
            'Classic Apparel' AS unit_name,
            pr.owner AS user_id,
            pr.name AS purchase_receipt,
            CASE 
                WHEN pr.posting_date IS NOT NULL AND gie.date_time IS NOT NULL 
                THEN DATEDIFF(pr.posting_date, DATE(gie.date_time))
                ELSE NULL
            END AS age
        FROM `tabGate Inward Entry` gie
        LEFT JOIN `tabPurchase Receipt` pr 
            ON pr.custom_gate_inward = gie.name 
            AND pr.docstatus < 2
        WHERE gie.docstatus = 1
        ORDER BY gie.date_time DESC
    """, as_dict=1)
    
    # Post-process data
    for row in data:
        # Format user ID to show full name
        if row.get("user_id"):
            user_full_name = frappe.db.get_value("User", row.user_id, "full_name")
            row["user_id"] = f"{row.user_id} ({user_full_name})" if user_full_name else row.user_id
        
        # Calculate age for pending entries (days since gate entry)
        if row.get("age") is None and row.get("inward_status") == "Pending" and row.get("gate_entry_date"):
            row["age"] = date_diff(getdate(), getdate(row["gate_entry_date"]))
    
    return data