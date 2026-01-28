# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import today


def execute(filters=None):
    """
    Open Purchase Order Report
    Shows item-wise open quantities with GRN reconciliation and overdue status
    (No filters applied)
    """
    columns = get_columns()
    data = get_data()
    # summary = get_report_summary(data) if data else None

    return columns, data, None, None, #summary


def get_columns():
    """Define report columns"""
    return [
        {
            "label": _("PO No"),
            "fieldname": "po_no",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 140,
        },
        {
            "label": _("PO Date"),
            "fieldname": "po_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("PO Type"),
            "fieldname": "po_type",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": _("Buyer"),
            "fieldname": "buyer",
            "fieldtype": "Link",
            "options": "Brand",
            "width": 120,
        },
        {
            "label": _("Merchant"),
            "fieldname": "merchant",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": _("Season"),
            "fieldname": "season",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("Party Name"),
            "fieldname": "party_name",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 180,
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150,
        },
        {
            "label": _("Size"),
            "fieldname": "size",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": _("Colour"),
            "fieldname": "colour",
            "fieldtype": "Data",
            "width": 90,
        },
        {
            "label": _("UOM"),
            "fieldname": "uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 70,
        },
        {
            "label": _("PO Qty"),
            "fieldname": "po_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
        },
        {
            "label": _("GRN Qty"),
            "fieldname": "grn_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
        },
        {
            "label": _("Return Qty"),
            "fieldname": "return_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
            "hidden": 1,
        },
        {
            "label": _("Cancelled Qty"),
            "fieldname": "cancelled_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
            "hidden": 1,
        },
        {
            "label": _("Bal Qty"),
            "fieldname": "bal_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 90,
        },
        {
            "label": _("Remarks"),
            "fieldname": "remarks",
            "fieldtype": "Data",
            "width": 150,
            "hidden": 1,
        },
        {
            "label": _("Days From PO"),
            "fieldname": "days_from_po",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": _("Due Days"),
            "fieldname": "due_days",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": _("Over Due Status"),
            "fieldname": "overdue_status",
            "fieldtype": "Data",
            "width": 110,
            "align": "center",
        },
    ]


def get_data():
    """Fetch open PO items with GRN reconciliation (no filters)"""
    current_date = today()

    query = """
        SELECT 
            PO.name AS po_no,
            PO.transaction_date AS po_date,
            PO.custom_purchase_order_type AS po_type,
            PO.custom_buyer AS buyer,
            Brand.custom_merchant AS merchant,
            PO.custom_season AS season,
            PO.supplier_name AS party_name,
            POI.item_code AS item_name,
            POI.custom_size AS size,
            POI.custom_colour AS colour,
            POI.uom AS uom,
            POI.qty AS po_qty,
            IFNULL(GRN.received_qty, 0) AS grn_qty,
            NULL AS return_qty,
            NULL AS cancelled_qty,
            (POI.qty - IFNULL(GRN.received_qty, 0)) AS bal_qty,
            NULL AS remarks,
            DATEDIFF(%(current_date)s, PO.transaction_date) AS days_from_po,
            GREATEST(DATEDIFF(%(current_date)s, POI.schedule_date), 0) AS due_days,
            CASE 
                WHEN POI.schedule_date IS NOT NULL 
                     AND POI.schedule_date < %(current_date)s 
                     AND (POI.qty - IFNULL(GRN.received_qty, 0)) > 0 
                THEN 'Over Due' 
                ELSE '' 
            END AS overdue_status
        FROM `tabPurchase Order` PO
        INNER JOIN `tabPurchase Order Item` POI 
            ON PO.name = POI.parent 
            AND POI.docstatus = 1
        LEFT JOIN `tabBrand` Brand 
            ON PO.custom_buyer = Brand.name
        LEFT JOIN (
            SELECT 
                pri.purchase_order_item,
                SUM(pri.qty) AS received_qty
            FROM `tabPurchase Receipt Item` pri
            INNER JOIN `tabPurchase Receipt` pr 
                ON pri.parent = pr.name 
                AND pr.docstatus = 1
            WHERE pri.purchase_order IS NOT NULL
            GROUP BY pri.purchase_order_item
        ) GRN ON GRN.purchase_order_item = POI.name
        WHERE 
            PO.docstatus = 1
            AND PO.status NOT IN ('Closed', 'Completed', 'Cancelled')
            AND (POI.qty - IFNULL(GRN.received_qty, 0)) > 0
        ORDER BY 
            PO.transaction_date DESC,
            PO.name,
            POI.idx
    """

    data = frappe.db.sql(
        query,
        {"current_date": current_date},
        as_dict=1,
    )

    # Apply visual styling for overdue items (client-side rendering)
    for row in data:
        if row.get("overdue_status") == "Over Due":
            row["overdue_status"] = '<span class="bold" style="color:#e74c3c">Over Due</span>'

    return data


def get_report_summary(data):
    """Generate summary cards for report header"""
    total_bal_qty = sum(d.get("bal_qty", 0) for d in data)
    overdue_count = sum(1 for d in data if "Over Due" in str(d.get("overdue_status", "")))

    return [
        {
            "value": len(data),
            "indicator": "Blue",
            "label": _("Open POs"),
            "datatype": "Int",
        },
        {
            "value": total_bal_qty,
            "indicator": "Orange",
            "label": _("Total Balance Qty"),
            "datatype": "Float",
        },
        {
            "value": overdue_count,
            "indicator": "Red",
            "label": _("Overdue POs"),
            "datatype": "Int",
        },
    ]