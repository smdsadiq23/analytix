# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)
    return columns, data, None, summary

def get_columns():
    return [
        {
            "label": "Purchase Order",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 150
        },
        {
            "label": "PO Date",
            "fieldname": "transaction_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 120
        },
        {
            "label": "PO Status",
            "fieldname": "po_status",
            "fieldtype": "Data",
            # Matches PO status options
            "width": 150
        },
        {
            "label": "GRN Created",
            "fieldname": "grn_created",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "GRN Completed",
            "fieldname": "grn_completed",
            "fieldtype": "Data",
            "width": 120
        }
    ]

def get_data(filters):
    # Base conditions for PO
    po_conditions = ["po.docstatus = 1"]
    po_conditions.append("po.status IN ('To Receive and Bill', 'To Bill')")
    
    values = {}

    # Apply filters
    if filters:
        if filters.get("company"):
            po_conditions.append("po.company = %(company)s")
            values["company"] = filters["company"]
        
        if filters.get("from_date"):
            po_conditions.append("po.transaction_date >= %(from_date)s")
            values["from_date"] = filters["from_date"]
        
        if filters.get("to_date"):
            po_conditions.append("po.transaction_date <= %(to_date)s")
            values["to_date"] = filters["to_date"]

    po_where = " AND ".join(po_conditions)

    query = f"""
        SELECT
            po.name AS purchase_order,
            po.transaction_date,
            po.company,
            po.status AS po_status,
            CASE 
                WHEN COUNT(grn.name) > 0 THEN 'Yes' 
                ELSE 'No' 
            END AS grn_created,
            CASE 
                WHEN COUNT(grn.name) = 0 THEN 'No'
                WHEN COUNT(grn.name) = SUM(CASE WHEN grn.docstatus = 1 THEN 1 ELSE 0 END) THEN 'Yes'
                ELSE 'Partial'
            END AS grn_completed
        FROM
            `tabPurchase Order` po
        LEFT JOIN
            `tabGoods Receipt Note` grn 
            ON grn.purchase_order = po.name 
            AND grn.docstatus != 2  -- Exclude cancelled GRNs
        WHERE
            {po_where}
        GROUP BY
            po.name, po.transaction_date, po.company, po.status
        ORDER BY
            po.transaction_date DESC, po.name DESC
    """

    return frappe.db.sql(query, values=values, as_dict=1)

def get_summary(data):
    if not data:
        return []

    grn_not_created = 0
    grn_partial = 0
    grn_completed = 0

    for row in data:
        if row.grn_created == "No":
            grn_not_created += 1
        elif row.grn_completed == "Partial":
            grn_partial += 1
        elif row.grn_completed == "Yes":
            grn_completed += 1

    total = len(data)

    return [
        {"value": total, "indicator": "blue", "label": _("Total POs"), "datatype": "Int"},
        {"value": grn_not_created, "indicator": "red", "label": _("No GRN Created"), "datatype": "Int"},
        {"value": grn_partial, "indicator": "orange", "label": _("Partial GRN"), "datatype": "Int"},
        {"value": grn_completed, "indicator": "green", "label": _("GRN Completed"), "datatype": "Int"}
    ]