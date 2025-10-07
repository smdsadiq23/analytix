# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Quarter"), "fieldname": "quarter", "fieldtype": "Data", "width": 120},
        {"label": _("Style"), "fieldname": "style", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": _("Buyer"), "fieldname": "buyer", "fieldtype": "Data", "width": 120},
        {"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
        {"label": _("OCN"), "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 130},
        {"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 110},
        {"label": _("Location"), "fieldname": "location", "fieldtype": "Data", "width": 100},
        {"label": _("Factory OCR"), "fieldname": "factory_ocr", "fieldtype": "Data", "width": 120},
        {"label": _("Review Status"), "fieldname": "review_status", "fieldtype": "Data", "width": 120},
        {"label": _("Order Qty"), "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Order Qnty + %"), "fieldname": "order_qty_plus", "fieldtype": "Float", "width": 120},
        {"label": _("Cut Qty"), "fieldname": "cut_qty", "fieldtype": "Float", "width": 90},
        {"label": _("Ship Qty"), "fieldname": "ship_qty", "fieldtype": "Float", "width": 90},
        {"label": _("Cut %"), "fieldname": "cut_percent", "fieldtype": "Percent", "width": 80},
        {"label": _("Cut to Ship"), "fieldname": "cut_to_ship_percent", "fieldtype": "Percent", "width": 110},
        {"label": _("Order to Ship"), "fieldname": "order_to_ship_percent", "fieldtype": "Percent", "width": 120},
    ]

def get_data(filters):
    order_data = get_order_summary()
    cut_data = get_cut_summary()
    ship_data = get_ship_summary()
    
    # Build lookup maps
    cut_map = {(d["style"], d["sales_order"]): flt(d["cut_qty"]) for d in cut_data}
    ship_map = {d["ocn"]: flt(d["ship_qty"]) for d in ship_data}
    
    result = []
    for row in order_data:
        fty_date = row.get("fty_date")
        if not fty_date:
            continue
        
        quarter = get_quarter_label(fty_date)
        month = get_month_label(fty_date)
        
        key = (row["style"], row["ocn"])
        order_qty_plus = flt(row["order_qty_plus"])
        cut_qty = cut_map.get(key, 0.0)
        ship_qty = ship_map.get(row["ocn"], 0.0)
        
        # Compute percentages safely
        cut_percent = (cut_qty / order_qty_plus * 100) if order_qty_plus else 0.0
        order_to_ship_percent = (ship_qty / order_qty_plus * 100) if order_qty_plus else 0.0
        cut_to_ship_percent = (ship_qty / cut_qty * 100) if cut_qty else 0.0
        
        result.append({
            "quarter": quarter,
            "style": row["style"],
            "buyer": row["buyer"],
            "description": row["description"],
            "ocn": row["ocn"],
            "month": month,
            "location": None,
            "factory_ocr": None,
            "review_status": None,
            "order_qty": flt(row["order_qty"]),
            "order_qty_plus": order_qty_plus,
            "cut_qty": cut_qty,
            "ship_qty": ship_qty,
            "cut_percent": flt(cut_percent, 2),
            "cut_to_ship_percent": flt(cut_to_ship_percent, 2),
            "order_to_ship_percent": flt(order_to_ship_percent, 2),
        })
    
    return result

# --- Data Fetching Functions ---

def get_order_summary():
    return frappe.db.sql("""
        SELECT 
            soi.item_code AS style,
            itm.brand AS buyer,
            itm.description,
            soi.parent AS ocn,
            soi.custom_ex_fty_date AS fty_date,
            SUM(soi.custom_order_qty) AS order_qty,
            SUM(soi.qty) AS order_qty_plus
        FROM `tabSales Order Item` soi
        INNER JOIN `tabItem` itm 
            ON soi.item_code = itm.name 
            AND itm.custom_select_master = 'Finished Goods'
        WHERE soi.custom_ex_fty_date IS NOT NULL
        GROUP BY soi.item_code, soi.parent, itm.brand, itm.description, soi.custom_ex_fty_date
    """, as_dict=1)

def get_cut_summary():
    return frappe.db.sql("""
        SELECT 
            cd.style,
            cci.sales_order,
            SUM(cci.confirmed_quantity) AS cut_qty
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` cc 
            ON cci.parent = cc.name AND cc.docstatus = 1
        INNER JOIN (
            SELECT name, style
            FROM `tabCut Docket`
            WHERE docstatus = 1
            GROUP BY name, style
        ) cd ON cc.cut_po_number = cd.name
        GROUP BY cd.style, cci.sales_order
    """, as_dict=1)

def get_ship_summary():
    """Get Ship Qty from the LAST operation (max idx in Operation Map)"""
    return frappe.db.sql("""
        SELECT
            so.name AS ocn,
            COALESCE(sa.completed_units, 0) AS ship_qty
        FROM `tabSales Order` so
        INNER JOIN (
            SELECT DISTINCT soi.parent
            FROM `tabSales Order Item` soi
            INNER JOIN `tabItem` itm ON itm.name = soi.item_code
            WHERE soi.custom_ex_fty_date IS NOT NULL
              AND itm.custom_select_master = 'Finished Goods'
        ) valid_so ON valid_so.parent = so.name
        LEFT JOIN (
            SELECT 
                tbc.sales_order,
                SUM(
                    CASE 
                        WHEN isl.log_status = 'Completed'
                         AND isl.status IN ('Counted', 'Activated', 'Pass')
                        THEN pi.quantity 
                        ELSE 0 
                    END
                ) AS completed_units
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
            INNER JOIN (
                SELECT parent, MAX(idx) AS max_idx
                FROM `tabOperation Map`
                GROUP BY parent
            ) last_op ON last_op.parent = tor.name
            INNER JOIN `tabOperation Map` opm 
                ON opm.parent = tor.name 
                AND opm.idx = last_op.max_idx
            INNER JOIN `tabProduction Item` pi 
                ON pi.tracking_order = tor.name 
                AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc 
                ON tc.name = pi.component 
                AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl 
                ON isl.production_item = pi.name 
                AND isl.operation = opm.operation
            WHERE 
                tbc.parentfield = 'component_bundle_configurations' 
                AND tbc.sales_order IS NOT NULL
            GROUP BY tbc.sales_order
        ) sa ON sa.sales_order = so.name
        WHERE so.docstatus = 1
    """, as_dict=1)

# --- Helper Functions ---

def get_quarter_label(date):
    d = getdate(date)
    year = d.year
    month = d.month
    if month >= 4:
        start_year = year
        end_year = year + 1
        q = (month - 4) // 3 + 1
    else:
        start_year = year - 1
        end_year = year
        q = 4
    return f"FY{str(start_year)[-2:]}-{str(end_year)[-2:]} - {q}"

def get_month_label(date):
    return formatdate(date, "MMMM yyyy")