# cuttingx/report/size_set_follow_up_report/size_set_follow_up_report.py

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("OCN"),
            "fieldname": "ocn",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 160
        },
        {
            "label": _("Buyer"),
            "fieldname": "buyer",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Merchant"),
            "fieldname": "custom_merchant",
            "fieldtype": "Link",
            "options": "User",
            "width": 140
        },
        {
            "label": _("Merchant Manager"),
            "fieldname": "custom_merchant_manager",
            "fieldtype": "Link",
            "options": "User",
            "width": 160
        },
        {
            "label": _("PPM Date"),
            "fieldname": "custom_ppm_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("PCD Committed"),
            "fieldname": "custom_pcd_committed",
            "fieldtype": "Date",
            "width": 160
        },
        {
            "label": _("Size Set Planned Date"),
            "fieldname": "custom_size_set_planned_date",
            "fieldtype": "Date",
            "width": 200
        },
        {
            "label": _("Size Set Cut Date"),
            "fieldname": "custom_size_set_cut_date",
            "fieldtype": "Date",
            "width": 160
        },
        {
            "label": _("Size Set Status"),
            "fieldname": "custom_size_set_status",
            "fieldtype": "Select",
            "options": "Under checking\nAwaiting pattern\nSewing Pending\nCompleted",
            "width": 160,
            "editable": 1  # ← This forces Frappe to allow inline editing
        }
    ]

def get_data(filters):
    conditions = ""
    if filters.get("from_date"):
        conditions += " AND so.delivery_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND so.delivery_date <= %(to_date)s"

    query = """
        SELECT
            so.name AS ocn,
            so.customer_name AS buyer,
            so.custom_merchant,
            so.custom_merchant_manager,
            so.custom_ppm_date,
            so.custom_pcd_committed,
            so.custom_size_set_planned_date,
            so.custom_size_set_cut_date,
            so.custom_size_set_status
        FROM `tabSales Order` so
        WHERE so.docstatus = 1
          {conditions}
        ORDER BY so.delivery_date DESC
    """.format(conditions=conditions)

    data = frappe.db.sql(query, filters, as_dict=1)
    return data
