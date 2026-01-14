# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, nowdate
import json


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": _("Sales Order No"), "fieldname": "sales_order_no", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": _("Style No"), "fieldname": "style_no", "fieldtype": "Data", "width": 120},
        {"label": _("Order Received Date"), "fieldname": "order_received_date", "fieldtype": "Date", "width": 120},
        {"label": _("Delivery Date"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 120},
        {"label": _("Order Qty"), "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Production Qty"), "fieldname": "production_qty", "fieldtype": "Float", "width": 120},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 80},
        {"label": _("Shipped Qty"), "fieldname": "shipped_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Ship Bal"), "fieldname": "shipped_bal", "fieldtype": "Float", "width": 100},
        {"label": _("Overdue Status"), "fieldname": "overdue_status", "fieldtype": "Data", "width": 120},
        {"label": _("Ship Record"), "fieldname": "ship_record", "fieldtype": "Link", "options": "Sales Order Ship Qty", "hidden": 1},
    ]


def get_data(filters):
    where_conditions = ["so.docstatus = 1"]
    params = {}

    if filters.get("from_date"):
        where_conditions.append("so.transaction_date >= %(from_date)s")
        params["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        where_conditions.append("so.transaction_date <= %(to_date)s")
        params["to_date"] = filters["to_date"]

    where_clause = " AND ".join(where_conditions)

    query = f"""
        SELECT
            so.customer AS customer,
            so.name AS sales_order_no,
            sod.custom_style AS style_no,
            so.transaction_date AS order_received_date,
            so.delivery_date AS delivery_date,
            SUM(sod.custom_order_qty) AS order_qty,
            sod.uom AS uom
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` sod ON sod.parent = so.name
        WHERE {where_clause}
        GROUP BY so.name, so.customer, sod.custom_style, sod.uom, 
                 so.transaction_date, so.delivery_date
        ORDER BY so.transaction_date DESC, so.name, sod.custom_style
    """
    
    base_rows = frappe.db.sql(query, params, as_dict=1)
    if not base_rows:
        return []

    sales_order_list = list({r["sales_order_no"] for r in base_rows})
    style_list = list({r["style_no"] for r in base_rows if r["style_no"]})

    # Production Qty
    production_rows = frappe.db.sql("""
        SELECT 
            tbc.sales_order AS sales_order_no,
            itm.custom_style_master AS style_no,
            COALESCE(SUM(pi.quantity), 0) AS production_qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
            AND tor.item IS NOT NULL AND tor.last_operation IS NOT NULL
        INNER JOIN `tabItem` itm ON itm.name = tor.item
        INNER JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name
            AND pi.bundle_configuration = tbc.name
        INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabItem Scan Log` isl ON isl.production_item = pi.name
            AND isl.operation = tor.last_operation
            AND isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
        WHERE tbc.sales_order IN %(sales_order_list)s
        GROUP BY tbc.sales_order, itm.custom_style_master
    """, {"sales_order_list": tuple(sales_order_list)}, as_dict=1)

    production_map = {(p["sales_order_no"], p["style_no"]): float(p["production_qty"] or 0) for p in production_rows}

    # Shipped Qty
    shipped_rows = frappe.db.sql("""
        SELECT name AS ship_record, sales_order AS sales_order_no, style AS style_no, shipped_qty
        FROM `tabSales Order Ship Qty`
        WHERE sales_order IN %(sales_order_list)s
          AND style IN %(style_list)s
    """, {
        "sales_order_list": tuple(sales_order_list),
        "style_list": tuple(style_list) if style_list else ('',)
    }, as_dict=1)

    shipped_map = {
        (s["sales_order_no"], s["style_no"]): {"shipped_qty": float(s["shipped_qty"] or 0), "ship_record": s["ship_record"]}
        for s in shipped_rows
    }

    final_rows = []
    today = getdate(nowdate())
    
    for row in base_rows:
        key = (row["sales_order_no"], row["style_no"])
        production_qty = production_map.get(key, 0)
        shipped_data = shipped_map.get(key, {"shipped_qty": 0, "ship_record": None})

        order_qty = float(row.get("order_qty") or 0)
        shipped_qty = float(shipped_data["shipped_qty"] or 0)

        # ✅ HIDE ROW IF SHIPPED IS COMPLETE
        if shipped_qty >= order_qty:
            continue  # ← Skip this row

        # ✅ ONLY INCLUDE INCOMPLETE ORDERS
        delivery_date = row.get("delivery_date")
        if delivery_date:
            delivery_date = getdate(delivery_date)
            if delivery_date > today:
                overdue_status = "No"
            else:
                overdue_status = "Yes"
        else:
            # If no delivery date, treat as overdue → "No"
            overdue_status = "Yes"

        row.update({
            "production_qty": production_qty,
            "shipped_qty": shipped_qty,
            "ship_record": shipped_data["ship_record"],
            "shipped_bal": order_qty - shipped_qty,
            "overdue_status": overdue_status  # ← "Yes" or "No"
        })

        final_rows.append(row)

    return final_rows

def update_shipped_qty(sales_order, style_no, shipped_qty):
    try:
        if not sales_order or not style_no:
            frappe.throw("Sales Order and Style No are required")

        shipped_qty = float(shipped_qty) if shipped_qty not in [None, ''] else 0

        existing = frappe.db.exists("Sales Order Ship Qty", {
            "sales_order": sales_order,
            "style": style_no
        })

        if existing:
            doc = frappe.get_doc("Sales Order Ship Qty", existing)
            doc.shipped_qty = shipped_qty
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc({
                "doctype": "Sales Order Ship Qty",
                "sales_order": sales_order,
                "style": style_no,
                "shipped_qty": shipped_qty
            })
            doc.insert(ignore_permissions=True)

        frappe.db.commit()
        return {
            "status": "success",
            "message": "Shipped quantity saved successfully",
            "record": doc.name
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error updating shipped quantity: {str(e)}")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def save_shipped_qty(data):
    try:
        if isinstance(data, str):
            data = json.loads(data)

        sales_order = data.get("sales_order_no")
        style_no = data.get("style_no")
        shipped_qty = data.get("shipped_qty")

        result = update_shipped_qty(sales_order, style_no, shipped_qty)

        if result["status"] == "success":
            order_qty = float(data.get("order_qty") or 0)
            shipped_qty_float = float(shipped_qty) if shipped_qty not in [None, ''] else 0
            shipped_bal = order_qty - shipped_qty_float

            delivery_date = data.get("delivery_date")
            today = getdate(nowdate())

            if delivery_date:
                delivery_date = getdate(delivery_date)
                if delivery_date < today:
                    overdue_status = "Shipped" if shipped_qty_float >= order_qty else "Overdue"
                else:
                    overdue_status = "Shipped" if shipped_qty_float >= order_qty else "On Track"
            else:
                overdue_status = "Shipped" if shipped_qty_float >= order_qty else "Pending"

            result.update({
                "shipped_bal": shipped_bal,
                "overdue_status": overdue_status
            })

        return result

    except Exception as e:
        frappe.log_error(f"Error in save_shipped_qty: {str(e)}")
        return {"status": "error", "message": str(e)}