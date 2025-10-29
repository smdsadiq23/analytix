# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data()
    return columns, data

def get_columns():
    return [
        {"label": _("Buyer"), "fieldname": "buyer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": _("Style"), "fieldname": "style", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": _("OCN"), "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 130},
        {"label": _("PCD"), "fieldname": "pcd", "fieldtype": "Date", "width": 100},
        {"label": _("Delivery Date"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 100},
        {"label": _("Order Quantity"), "fieldname": "order_quantity", "fieldtype": "Float", "width": 120},
        {"label": _("Fabric Available"), "fieldname": "fabric_available", "fieldtype": "Data", "width": 120},  # NULL in original
        {"label": _("Cut Quantity"), "fieldname": "cut_quantity", "fieldtype": "Float", "width": 110},
        {"label": _("Cut Balance against Order Qty"), "fieldname": "cut_balance", "fieldtype": "Float", "width": 180},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 200},
    ]

def get_data():
    # Get all Sales Orders with Finished Goods item
    so_list = frappe.db.sql("""
        SELECT 
            so.name AS ocn,
            so.customer AS buyer,
            so.delivery_date,
            so.total_qty AS order_quantity,
            so.custom_report_remarks AS remarks
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` sod ON sod.parent = so.name
        INNER JOIN `tabItem` item ON item.name = sod.item_code
        WHERE 
            so.docstatus = 1
            AND item.custom_select_master = 'Finished Goods'
            AND sod.name = (
                SELECT sub_sod.name
                FROM `tabSales Order Item` sub_sod
                INNER JOIN `tabItem` sub_item ON sub_item.name = sub_sod.item_code
                WHERE sub_sod.parent = so.name
                  AND sub_item.custom_select_master = 'Finished Goods'
                ORDER BY sub_sod.idx
                LIMIT 1
            )
        ORDER BY so.delivery_date ASC
    """, as_dict=1)

    # Get PCD (latest modified date from Can Cut)
    pcd_map = frappe._dict(frappe.db.sql("""
        SELECT sales_order, MAX(DATE(modified)) AS pcd
        FROM `tabCan Cut`
        GROUP BY sales_order
    """))

    # Get Cut Quantity
    cut_qty_map = frappe._dict(frappe.db.sql("""
        SELECT sales_order, SUM(confirmed_quantity) AS cut_qty
        FROM `tabCut Confirmation Item`
        GROUP BY sales_order
    """))

    # Build final data
    data = []
    for so in so_list:
        ocn = so.ocn
        cut_qty = flt(cut_qty_map.get(ocn))
        order_qty = flt(so.order_quantity)
        balance = order_qty - cut_qty

        data.append({
            "buyer": so.buyer,
            "style": frappe.db.get_value("Sales Order Item", {
                "parent": ocn,
                "item_code": ["in", frappe.db.sql_list("""
                    SELECT name FROM `tabItem` 
                    WHERE custom_select_master = 'Finished Goods'
                """)]
            }, "item_code") or "",  # You may refine this
            "ocn": ocn,
            "pcd": pcd_map.get(ocn),
            "delivery_date": so.delivery_date,
            "order_quantity": order_qty,
            "fabric_available": None,  # as per original
            "cut_quantity": cut_qty,
            "cut_balance": balance,
            "remarks": so.remarks or ""
        })

    return data

def flt(val):
    return float(val or 0)