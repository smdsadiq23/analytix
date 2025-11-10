# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    return columns, data, None, chart

def get_columns():
    return [
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Purchase Order Count",
            "fieldname": "count",
            "fieldtype": "Int",
            "width": 150
        }
    ]

def get_data(filters):
    conditions = ["po.docstatus = 1"]
    values = {}

    if filters:
        if filters.get("company"):
            conditions.append("po.company = %(company)s")
            values["company"] = filters["company"]
        if filters.get("from_date"):
            conditions.append("po.transaction_date >= %(from_date)s")
            values["from_date"] = filters["from_date"]
        if filters.get("to_date"):
            conditions.append("po.transaction_date <= %(to_date)s")
            values["to_date"] = filters["to_date"]

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT 
            po.status,
            COUNT(*) AS count
        FROM `tabPurchase Order` po
        WHERE {where_clause}
        GROUP BY po.status
        ORDER BY count DESC
    """
    return frappe.db.sql(query, values=values, as_dict=1)

def get_chart(data):
    if not data:
        return None
        
    return {
        "data": {
            "labels": [d.status for d in data],
            "datasets": [{
                "name": "Purchase Orders",
                "values": [d.count for d in data],
                "chartType": "donut"
            }]
        },
        "type": "donut",
        "height": 300,
        "colors": ["#7cd6fd", "#7467ef", "#f89f4f", "#5e6873", "#ff9900"]
    }