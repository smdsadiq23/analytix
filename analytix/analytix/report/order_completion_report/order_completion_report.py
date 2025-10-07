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
        {"label": _("Good Garments"), "fieldname": "good_garments", "fieldtype": "Float", "width": 100},
        {"label": _("Allowed Rejection"), "fieldname": "allowed_rejection", "fieldtype": "int", "width": 80},
        {"label": _("Actual Rejection"), "fieldname": "actual_rejection", "fieldtype": "Int", "width": 100},
        {"label": _("Excess Rejection"), "fieldname": "excess_rejection", "fieldtype": "Int", "width": 100},
        {"label": _("Missing Units"), "fieldname": "missing_units", "fieldtype": "Float", "width": 100},
        {"label": _("FOB"), "fieldname": "fob", "fieldtype": "Currency", "width": 100},        
        {"label": _("Short Cutting Loss"), "fieldname": "short_cutting_loss", "fieldtype": "Currency", "width": 120},
        {"label": _("Value Loss"), "fieldname": "value_loss", "fieldtype": "Currency", "width": 120},        
    ]

def get_data(filters):
    order_data = get_order_summary()
    cut_data = get_cut_summary()
    ship_data = get_ship_summary()
    rejection_data = get_rejection_summary()
    
    # Build lookup maps
    cut_map = {(d["style"], d["sales_order"]): flt(d["cut_qty"]) for d in cut_data}
    ship_map = {(d["style"], d["ocn"]): flt(d["ship_qty"]) for d in ship_data}
    rejection_map = {(d["style"], d["ocn"]): d["actual_rejections"] for d in rejection_data}
    
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
        ship_qty = ship_map.get(key, 0.0)
        actual_rejection = rejection_map.get(key, 0)
        
        # Compute percentages safely
        cut_percent = (cut_qty / order_qty_plus * 100) if order_qty_plus else 0.0
        order_to_ship_percent = (ship_qty / order_qty_plus * 100) if order_qty_plus else 0.0
        cut_to_ship_percent = (ship_qty / cut_qty * 100) if cut_qty else 0.0
        allowed_rejection = (cut_qty * 0.005) if cut_qty else 0
        excess_rejection = max(0, actual_rejection - allowed_rejection)
        fob = flt(row.get("fob")) if row.get("fob") is not None else None

        # Initialize losses as None (will show blank if not calculated)
        short_cutting_loss = None
        value_loss = None

        if fob is not None and fob > 0:
            # ✅ Short Cutting Loss: only if cut_qty > 0
            if cut_qty > 0:
                short_cutting_loss = (order_qty_plus - cut_qty) * fob
                short_cutting_loss = max(0, short_cutting_loss)  # Ensure non-negative				
            
            # ✅ Value Loss: only if ship_qty > 0
            if ship_qty > 0:
                value_loss = (cut_qty - ship_qty) * fob
                value_loss = max(0, value_loss)  # Ensure non-negative       
        
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
            "good_garments": flt(row.get("good_garments"), 0) or "",
            "allowed_rejection": flt(allowed_rejection, 0),
            "actual_rejection": actual_rejection,
            "excess_rejection": excess_rejection,
            "missing_units": flt(row.get("missing_units")) or "",  
            "fob": flt(row.get("fob")) or "",     
            "short_cutting_loss": short_cutting_loss or "",
            "value_loss": value_loss or "",         
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
            SUM(soi.qty) AS order_qty_plus,
            MAX(soi.custom_good_garments) AS good_garments,
            MAX(soi.custom_missing_units) AS missing_units,
            MAX(soi.custom_fob) AS fob
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
    """Get Ship Qty per Sales Order + Item from the LAST operation stored on Tracking Order"""
    return frappe.db.sql("""
        SELECT
            so.name AS ocn,
            sa.item AS style,
            COALESCE(SUM(sa.completed_units), 0) AS ship_qty
        FROM `tabSales Order` so
        INNER JOIN (
            SELECT DISTINCT soi.parent, soi.item_code
            FROM `tabSales Order Item` soi
            INNER JOIN `tabItem` itm ON itm.name = soi.item_code
            WHERE soi.custom_ex_fty_date IS NOT NULL
              AND itm.custom_select_master = 'Finished Goods'
        ) valid_so
            ON valid_so.parent = so.name
        LEFT JOIN (
            SELECT
                tbc.sales_order,
                tor.item,
                SUM(
                    CASE
                        WHEN isl.log_status = 'Completed'
                         AND isl.status IN ('Counted', 'Activated', 'Pass')
                        THEN pi.quantity
                        ELSE 0
                    END
                ) AS completed_units
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor
                ON tor.name = tbc.parent
               AND tor.item IS NOT NULL
               AND tor.last_operation IS NOT NULL
            INNER JOIN `tabProduction Item` pi
                ON  pi.tracking_order = tor.name
                AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc
                ON tc.name = pi.component
               AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl
                ON isl.production_item = pi.name
               AND isl.operation = tor.last_operation
            WHERE tbc.parentfield = 'component_bundle_configurations'
              AND tbc.sales_order IS NOT NULL
            GROUP BY tbc.sales_order, tor.item
        ) sa
            ON sa.sales_order = so.name
           AND sa.item = valid_so.item_code
        WHERE so.docstatus = 1
        GROUP BY so.name, valid_so.item_code
    """, as_dict=1)

def get_rejection_summary():
    """Get count of rejection scan logs per Sales Order + Style"""
    return frappe.db.sql("""
        SELECT
            tbc.sales_order AS ocn,
            tor.item AS style,
            COUNT(isl.name) AS actual_rejections
        FROM `tabTracking Order` tor
        INNER JOIN `tabTracking Order Bundle Configuration` tbc 
            ON tbc.parent = tor.name
            AND tbc.parentfield = 'component_bundle_configurations'
            AND tbc.sales_order IS NOT NULL
        INNER JOIN `tabProduction Item` pi 
            ON pi.tracking_order = tor.name 
            AND pi.bundle_configuration = tbc.name
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component 
            AND tc.is_main = 1
        INNER JOIN `tabItem Scan Log` isl 
            ON isl.production_item = pi.name
            AND isl.status LIKE '%Reject%'
        INNER JOIN (
            SELECT DISTINCT soi.parent AS sales_order, soi.item_code
            FROM `tabSales Order Item` soi
            INNER JOIN `tabItem` itm 
                ON itm.name = soi.item_code 
                AND itm.custom_select_master = 'Finished Goods'
            WHERE soi.custom_ex_fty_date IS NOT NULL
        ) valid_so 
            ON valid_so.sales_order = tbc.sales_order 
            AND valid_so.item_code = tor.item
        GROUP BY tbc.sales_order, tor.item
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
