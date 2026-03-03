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
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 120},
        {"label": _("PCD"), "fieldname": "pcd", "fieldtype": "Date", "width": 100},
        {"label": _("Delivery Date"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 100},
        {"label": _("Order Quantity"), "fieldname": "order_quantity", "fieldtype": "Int", "width": 120},
        {"label": _("Fabric Available"), "fieldname": "fabric_available", "fieldtype": "Data", "width": 120},
        {"label": _("Cut Quantity"), "fieldname": "cut_quantity", "fieldtype": "Int", "width": 110},
        {"label": _("Cut Balance against Order Qty"), "fieldname": "cut_balance", "fieldtype": "Int", "width": 180},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 200},
    ]

def get_data():
    # Get Sales Orders that have Cut Docket AND (No Cut Confirmation OR Cut Confirmation >= 2026-02-01)
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
            AND (so.custom_consumption_status IS NULL OR so.custom_consumption_status = 'Inprogress')
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
            -- Must have Cut Docket
            AND EXISTS (
                SELECT 1 
                FROM `tabCut Docket Item` cdi
                WHERE cdi.sales_order = so.name
            )
            -- AND (No Cut Confirmation OR Cut Confirmation >= 2026-02-01)
            AND (
                -- No Cut Confirmation exists
                NOT EXISTS (
                    SELECT 1 
                    FROM `tabCut Confirmation Item` cci
                    WHERE cci.sales_order = so.name
                )
                OR
                -- Cut Confirmation exists on or after 2026-02-01
                EXISTS (
                    SELECT 1 
                    FROM `tabCut Confirmation Item` cci
                    INNER JOIN `tabCut Confirmation` cc ON cci.parent = cc.name
                    WHERE cci.sales_order = so.name
                      AND cc.creation >= '2026-02-01'
                )
            )
        ORDER BY so.delivery_date ASC
    """, as_dict=1)

    # Get PCD (latest modified date from Can Cut)
    pcd_map = frappe._dict(frappe.db.sql("""
        SELECT sales_order, MAX(DATE(modified)) AS pcd
        FROM `tabCan Cut`
        GROUP BY sales_order
    """))

    # Get Cut Quantity and Unit (only for Cut Confirmations created on or after 2026-02-01)
    cut_data = frappe.db.sql("""
        SELECT 
            cci.sales_order,
            fbu.factory_name AS unit,
            SUM(cci.confirmed_quantity) AS cut_qty
        FROM `tabCut Confirmation Item` cci
        LEFT JOIN `tabCut Confirmation` cc ON cci.parent = cc.name
        LEFT JOIN `tabFactory Business Unit` fbu ON cc.factory_business_unit = fbu.name
        WHERE cc.creation >= '2026-02-01'
        GROUP BY cci.sales_order, cc.factory_business_unit
    """, as_dict=1)

    # Create a map: sales_order -> {unit, cut_qty}
    cut_map = {}
    for row in cut_data:
        if row.sales_order not in cut_map:
            cut_map[row.sales_order] = {"unit": row.unit, "cut_qty": flt(row.cut_qty)}
        else:
            # If multiple units, sum quantities
            cut_map[row.sales_order]["cut_qty"] += flt(row.cut_qty)

    # Build final data
    data = []
    for so in so_list:
        ocn = so.ocn
        cut_info = cut_map.get(ocn, {})
        cut_qty = cut_info.get("cut_qty", 0)
        unit = cut_info.get("unit", "")
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
            }, "item_code") or "",
            "ocn": ocn,
            "unit": unit,
            "pcd": pcd_map.get(ocn),
            "delivery_date": so.delivery_date,
            "order_quantity": order_qty,
            "fabric_available": None,
            "cut_quantity": cut_qty,
            "cut_balance": balance,
            "remarks": so.remarks or ""
        })

    return data

def flt(val):
    return float(val or 0)