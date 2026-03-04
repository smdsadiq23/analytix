# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt


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
            "frozen": 1            
        },
        {
            "label": _("Buyer"),
            "fieldname": "buyer",
            "fieldtype": "Data",
            "frozen": 1            
        },
        {
            "label": _("Style"),
            "fieldname": "style",
            "fieldtype": "Data",
            "frozen": 1            
        },
        {
            "label": _("Colour"),
            "fieldname": "colour",
            "fieldtype": "Data",
            "frozen": 1            
        },
        {
            "label": _("Merchant"),
            "fieldname": "custom_merchant",
            "fieldtype": "Link",
            "options": "User",
        },
        {
            "label": _("Merchant Manager"),
            "fieldname": "custom_merchant_manager",
            "fieldtype": "Link",
            "options": "User",
        },
        {
            "label": _("PPM Date"),
            "fieldname": "ppm_date",
            "fieldtype": "Date",
        },
        {
            "label": _("PCD Committed"),
            "fieldname": "pcd_committed",
            "fieldtype": "Date",
        },
        {
            "label": _("Size Set Planned Date"),
            "fieldname": "size_set_planned_date",
            "fieldtype": "Date",
        },
        {
            "label": _("Size Set Cut Date"),
            "fieldname": "size_set_cut_date",
            "fieldtype": "Date",
        },
        {
            "label": _("Size Set Status"),
            "fieldname": "size_set_status",
            "fieldtype": "Select",
            "options": "Pattern Issues\nSewing Pending\nUnder Checking\nCompleted",
            "editable": 1
        },
        {
            "label": _("Completion On"),
            "fieldname": "completion_on",
            "fieldtype": "Date",
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
            soi.parent                  AS ocn,
            so.customer_name            AS buyer,
            soi.custom_style            AS style,
            soi.custom_color            AS colour,
            so.custom_merchant,
            so.custom_merchant_manager,
            sst.ppm_date,
            sst.pcd_committed,
            sst.size_set_planned_date,
            sst.size_set_cut_date,
            sst.size_set_status,
            sst.completion_on,
            sst.name                    AS tracker_name
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so
            ON so.name = soi.parent
        LEFT JOIN `tabSize Set Tracker` sst
            ON  sst.ocn    = soi.parent
            AND sst.style  = soi.custom_style
            AND sst.colour = soi.custom_color
        WHERE so.docstatus <= 1
          {conditions}
        GROUP BY
            soi.parent,
            soi.custom_style,
            soi.custom_color
        ORDER BY
            FIELD(sst.size_set_status,
                'Pattern Issues',
                'Sewing Pending',
                'Under Checking',
                'Completed'
            ),
            so.delivery_date DESC
    """.format(conditions=conditions)

    data = frappe.db.sql(query, filters, as_dict=1)
    return data