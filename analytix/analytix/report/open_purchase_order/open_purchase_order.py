# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import today


def execute(filters=None):
    """
    Open Purchase Order Report
    - Shows ALL PO items (open + fully received) for tracking
    - For open items (Bal Qty > 0): Uses current date for calculations
    - For closed items (Bal Qty = 0): Uses latest GRN date for calculations
    """
    columns = get_columns()
    data = get_data()
    return columns, data, None, None, None  # Summary intentionally disabled per user code


def get_columns():
    """Define report columns"""
    return [
        {"label": _("PO No"), "fieldname": "po_no", "fieldtype": "Link", "options": "Purchase Order", "width": 140},
        {"label": _("PO Date"), "fieldname": "po_date", "fieldtype": "Date", "width": 100},
        {"label": _("PO Type"), "fieldname": "po_type", "fieldtype": "Data", "width": 100},
        {"label": _("Buyer"), "fieldname": "buyer", "fieldtype": "Link", "options": "Brand", "width": 120},
        {"label": _("Merchant"), "fieldname": "merchant", "fieldtype": "Data", "width": 120},
        {"label": _("Season"), "fieldname": "season", "fieldtype": "Data", "width": 90},
        {"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Link", "options": "Supplier", "width": 180},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Size"), "fieldname": "size", "fieldtype": "Data", "width": 80},
        {"label": _("Colour"), "fieldname": "colour", "fieldtype": "Data", "width": 90},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
        {"label": _("PO Qty"), "fieldname": "po_qty", "fieldtype": "Float", "precision": 2, "width": 90},
        {"label": _("GRN Qty"), "fieldname": "grn_qty", "fieldtype": "Float", "precision": 2, "width": 90},
        {"label": _("Return Qty"), "fieldname": "return_qty", "fieldtype": "Float", "precision": 2, "width": 90, "hidden": 1},
        {"label": _("Cancelled Qty"), "fieldname": "cancelled_qty", "fieldtype": "Float", "precision": 2, "width": 90, "hidden": 1},
        {"label": _("Bal Qty"), "fieldname": "bal_qty", "fieldtype": "Float", "precision": 2, "width": 90},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 150, "hidden": 1},
        {"label": _("Days From PO"), "fieldname": "days_from_po", "fieldtype": "Int", "width": 110},
        {"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 90},
        {"label": _("From Due Date"), "fieldname": "due_days", "fieldtype": "Int", "width": 90},
        {"label": _("Over Due Status"), "fieldname": "overdue_status", "fieldtype": "Data", "width": 110, "align": "center"},
    ]


def get_data():
    """Fetch PO items with intelligent date calculations based on receipt status"""
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
            -- CRITICAL: Days From PO logic
            CASE 
                WHEN (POI.qty - IFNULL(GRN.received_qty, 0)) > 0 
                    THEN DATEDIFF(%(current_date)s, PO.transaction_date)  -- Open item: current date
                    ELSE DATEDIFF(GRN.latest_grn_date, PO.transaction_date) -- Closed item: latest GRN date
            END AS days_from_po,
            POI.schedule_date AS due_date,
            -- CRITICAL: From Due Date logic (can be negative for early receipts)
            CASE 
                WHEN (POI.qty - IFNULL(GRN.received_qty, 0)) > 0 
                    THEN GREATEST(DATEDIFF(%(current_date)s, POI.schedule_date), 0)  -- Open: non-negative days overdue
                    ELSE DATEDIFF(GRN.latest_grn_date, POI.schedule_date)            -- Closed: actual diff (neg=early, pos=late)
            END AS due_days,
            -- Overdue status ONLY for open items
            CASE 
                WHEN (POI.qty - IFNULL(GRN.received_qty, 0)) > 0 
                     AND POI.schedule_date IS NOT NULL 
                     AND POI.schedule_date < %(current_date)s 
                THEN 'Over Due' 
                ELSE '' 
            END AS overdue_status
        FROM `tabPurchase Order` PO
        INNER JOIN `tabPurchase Order Item` POI 
            ON PO.name = POI.parent AND POI.docstatus = 1
        LEFT JOIN `tabBrand` Brand 
            ON PO.custom_buyer = Brand.name
        LEFT JOIN (
            -- AGGREGATES ALL GRNs PER PO ITEM: sums qty + captures LATEST GRN date
            SELECT 
                pri.purchase_order_item,
                SUM(pri.qty) AS received_qty,
                MAX(pr.posting_date) AS latest_grn_date  -- Critical for closed item calculations
            FROM `tabPurchase Receipt Item` pri
            INNER JOIN `tabPurchase Receipt` pr 
                ON pri.parent = pr.name AND pr.docstatus = 1
            WHERE pri.purchase_order IS NOT NULL
            GROUP BY pri.purchase_order_item
        ) GRN ON GRN.purchase_order_item = POI.name
        WHERE 
            PO.docstatus = 1
            AND PO.status NOT IN ('Closed', 'Completed', 'Cancelled')
            -- INCLUDES BOTH OPEN AND FULLY RECEIVED ITEMS (balance=0)
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

    # Visual highlighting for overdue open items ONLY
    for row in data:
        if row.get("overdue_status") == "Over Due":
            row["overdue_status"] = '<span class="bold" style="color:#e74c3c">Over Due</span>'
    
    return data