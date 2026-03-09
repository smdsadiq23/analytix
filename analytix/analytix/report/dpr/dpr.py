# Copyright (c) 2025, Cognitonx Logic India Private limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from collections import defaultdict

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data_optimized(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("OCN"), "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": _("Style"), "fieldname": "style", "fieldtype": "Data", "width": 120},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 100},
        {"label": _("Colour"), "fieldname": "colour", "fieldtype": "Data", "width": 100},
        {"label": _("Ord Qty"), "fieldname": "order_qty", "fieldtype": "Int", "width": 80},
        {"label": _("Cut Qty"), "fieldname": "cut_quantity", "fieldtype": "Int", "width": 80},
        {"label": _("Cut %"), "fieldname": "cut_pct", "fieldtype": "Percent", "width": 100, "precision": 1},
        {"label": _("Cut Bal"), "fieldname": "cut_balance", "fieldtype": "Int", "width": 80},
        {"label": _("Last Cut Date"), "fieldname": "last_cut_date", "fieldtype": "Date", "width": 120},
        {"label": _("CCR Status"), "fieldname": "custom_consumption_status", "fieldtype": "Data", "width": 100},
        {"label": _("Sew Qty"), "fieldname": "sew_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Sew Bal"), "fieldname": "sew_balance", "fieldtype": "Int", "width": 80},
        {"label": _("Scan Qty"), "fieldname": "scan_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Pack Qty"), "fieldname": "pack_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Pack Bal"), "fieldname": "pack_balance", "fieldtype": "Int", "width": 90},
        {"label": _("Ship Qty"), "fieldname": "ship_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Cut to Pack %"), "fieldname": "cut_to_pack", "fieldtype": "Percent", "width": 120, "precision": 1},
        {"label": _("Order to Pack %"), "fieldname": "order_to_pack", "fieldtype": "Percent", "width": 120, "precision": 1},
        {"label": _("OCR Status"), "fieldname": "ocr_status", "fieldtype": "Data", "width": 120},
        {"label": _("Dispatch Qty"), "fieldname": "dispatch_quantity", "fieldtype": "Int", "width": 120},
        {"label": _("Bal to Dispatch"), "fieldname": "bal_to_dispatch", "fieldtype": "Int", "width": 120},
        {"label": _("Dead Stock"), "fieldname": "dead_stock", "fieldtype": "Int", "width": 100},
    ]

_APPROVAL_PRIORITY = {
    "Inprogress": 0,
    "Yet to Confirm": 1,
    "Completed": 2,
    "Approved": 3,
    "App with Replenishment": 4,
}

def _pct(numerator, denominator):
    return (numerator / denominator * 100.0) if denominator else 0.0

def get_data_optimized(filters):
    """
    Optimized version with fewer SQL queries and more Python processing
    """
    # --- 1. Main query with all base data ---
    base_query = """
        SELECT 
            so.name AS ocn,
            item.custom_style_master AS style,
            sod.custom_color AS colour,
            SUM(sod.custom_order_qty) AS order_qty,
            so.custom_approval AS custom_consumption_status,
            so.custom_consumption_status AS status,
            so.delivery_date
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` sod ON sod.parent = so.name
        INNER JOIN `tabItem` item ON item.name = sod.item_code
        WHERE so.docstatus = 1
        GROUP BY so.name, item.custom_style_master, sod.custom_color
        ORDER BY so.delivery_date, so.name, sod.custom_color
    """
    
    base_rows = frappe.db.sql(base_query, as_dict=1)
    
    if not base_rows:
        return []
    
    ocn_list = tuple({r["ocn"] for r in base_rows})
    
    # --- 2. Cut data query (separate for better performance) ---
    cut_query = """
        SELECT 
            cci.sales_order AS ocn,
            cd.color AS colour,
            MAX(fbu.factory_name) AS unit,
            SUM(COALESCE(cci.confirmed_quantity, 0)) AS cut_quantity,
            MAX(con.creation) AS last_cut_date,
            MAX(cc.with_replenishment) AS with_replenishment
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` con ON con.name = cci.parent AND con.docstatus = 1
        INNER JOIN `tabCut Docket` cd ON cd.name = con.cut_po_number
        LEFT JOIN `tabFactory Business Unit` fbu ON fbu.name = cd.factory_business_unit
        LEFT JOIN `tabCan Cut` cc ON cc.sales_order = cci.sales_order AND cc.colour = cd.color
        WHERE cci.docstatus = 1 AND cci.sales_order IN %(ocn_list)s
        GROUP BY cci.sales_order, cd.color
    """
    
    cut_data = frappe.db.sql(cut_query, {"ocn_list": ocn_list}, as_dict=1)
    
    # --- 3. Factory OCR data query ---
    factory_query = """
        SELECT 
            fo.ocn AS ocn,
            foi.colour AS colour,
            SUM(COALESCE(foi.scan_quantity, 0)) AS scan_quantity,
            SUM(COALESCE(foi.pack_quantity, 0)) AS pack_quantity,
            SUM(COALESCE(foi.ship_quantity, 0)) AS ship_quantity,
            AVG(COALESCE(foi.cut_to_ship, 0)) AS cut_to_ship,
            AVG(COALESCE(foi.order_to_ship, 0)) AS order_to_ship,
            MAX(fo.with_replenishment) AS with_replenishment,
            MAX(fo.status) AS factory_status
        FROM `tabFactory OCR` fo
        INNER JOIN `tabFactory OCR Item` foi ON foi.parent = fo.name
        WHERE fo.status = 'Approved'
            AND fo.docstatus < 2
            AND fo.ocn IN %(ocn_list)s
        GROUP BY fo.ocn, foi.colour
    """
    
    factory_data = frappe.db.sql(factory_query, {"ocn_list": ocn_list}, as_dict=1)
    
    # --- 4. Production data query (Sew & Scan) ---
    production_query = """
        SELECT 
            tbc.sales_order AS ocn,
            itm.custom_colour_name AS colour,
            SUM(DISTINCT 
                CASE 
                    WHEN isl_sew.production_item IS NOT NULL 
                    THEN COALESCE(pi.quantity, 0) 
                    ELSE 0 
                END
            ) AS sew_quantity,
            SUM(DISTINCT 
                CASE 
                    WHEN isl_scan.production_item IS NOT NULL 
                    THEN COALESCE(pi.quantity, 0) 
                    ELSE 0 
                END
            ) AS scan_quantity
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent AND tor.item IS NOT NULL
        INNER JOIN `tabItem` itm ON itm.name = tor.item
        INNER JOIN `tabProduction Item` pi ON pi.tracking_order = tor.name 
            AND pi.bundle_configuration = tbc.name
        INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        LEFT JOIN `tabItem Scan Log` isl_sew ON isl_sew.production_item = pi.name
            AND isl_sew.operation LIKE 'Sewing Incoming%%'
            AND isl_sew.log_status = 'Completed'
            AND isl_sew.status IN ('Counted', 'Activated', 'Pass')
        LEFT JOIN `tabCut Kit Plan Bundle Details` ckpbd ON ckpbd.production_item_id = pi.name
        LEFT JOIN `tabCut Kit Plan` ckp ON ckp.name = ckpbd.parent
        LEFT JOIN `tabItem Scan Log` isl_scan ON isl_scan.production_item = pi.name
            AND isl_scan.operation = ckp.last_operation
            AND isl_scan.log_status = 'Completed'
            AND isl_scan.status IN ('Counted', 'Activated', 'Pass')
        WHERE tbc.sales_order IN %(ocn_list)s
        GROUP BY tbc.sales_order, itm.custom_colour_name
    """
    
    production_data = frappe.db.sql(production_query, {"ocn_list": ocn_list}, as_dict=1)
    
    # --- 5. Build lookup dictionaries ---
    cut_map = {}
    for d in cut_data:
        cut_map[(d["ocn"], d["colour"])] = {
            "cut_quantity": float(d.get("cut_quantity") or 0),
            "last_cut_date": d.get("last_cut_date"),
            "unit": d.get("unit") or "",
            "with_replenishment": int(d.get("with_replenishment") or 0)
        }
    
    factory_map = {}
    for d in factory_data:
        factory_map[(d["ocn"], d["colour"])] = {
            "scan_quantity": float(d.get("scan_quantity") or 0),
            "pack_quantity": float(d.get("pack_quantity") or 0),
            "ship_quantity": float(d.get("ship_quantity") or 0),
            "cut_to_ship": float(d.get("cut_to_ship") or 0),
            "order_to_ship": float(d.get("order_to_ship") or 0),
            "with_replenishment": int(d.get("with_replenishment") or 0),
            "factory_status": d.get("factory_status") or "",
        }
    
    production_map = {}
    for d in production_data:
        production_map[(d["ocn"], d["colour"])] = {
            "sew_quantity": float(d.get("sew_quantity") or 0),
            "scan_quantity": float(d.get("scan_quantity") or 0),
        }
    
    # --- 6. Dead stock only for Verified OCNs ---
    verified_ocns = tuple({r["ocn"] for r in base_rows if r.get("status") == "Verified"})
    dead_stock_map = {}
    
    if verified_ocns:
        # Simplified dead stock query without subquery
        dead_stock_query = """
            SELECT 
                grn.ocn AS ocn,
                gri.color AS colour,
                SUM(COALESCE(gri.received_quantity, 0)) - COALESCE((
                    SELECT SUM(COALESCE(lrd.actual_total, 0))
                    FROM `tabCutting Lay Record` clr2
                    LEFT JOIN `tabLay Roll Details` lrd ON lrd.parent = clr2.name
                    WHERE clr2.ocn = grn.ocn 
                        AND clr2.colour = gri.color 
                        AND clr2.docstatus = 1
                ), 0) AS dead_stock
            FROM `tabGoods Receipt Note` grn
            INNER JOIN `tabGoods Receipt Item` gri ON gri.parent = grn.name
            WHERE grn.docstatus = 1 
                AND grn.ocn IN %(verified_ocns)s
            GROUP BY grn.ocn, gri.color
            
            UNION
            
            SELECT 
                clr.ocn AS ocn,
                clr.colour AS colour,
                0 - SUM(COALESCE(lrd.actual_total, 0)) AS dead_stock
            FROM `tabCutting Lay Record` clr
            LEFT JOIN `tabLay Roll Details` lrd ON lrd.parent = clr.name
            WHERE clr.docstatus = 1 
                AND clr.ocn IN %(verified_ocns)s
                AND NOT EXISTS (
                    SELECT 1 
                    FROM `tabGoods Receipt Note` grn2
                    INNER JOIN `tabGoods Receipt Item` gri2 ON gri2.parent = grn2.name
                    WHERE grn2.ocn = clr.ocn 
                        AND gri2.color = clr.colour 
                        AND grn2.docstatus = 1
                )
            GROUP BY clr.ocn, clr.colour
        """
        
        dead_stock_data = frappe.db.sql(dead_stock_query, {"verified_ocns": verified_ocns}, as_dict=1)
        dead_stock_map = {(d["ocn"], d["colour"]): float(d.get("dead_stock") or 0) for d in dead_stock_data}
    
    # --- 7. Process all rows in Python ---
    _empty_factory = {
        "scan_quantity": 0, "pack_quantity": 0, "ship_quantity": 0,
        "cut_to_ship": 0, "order_to_ship": 0,
        "with_replenishment": 0, "factory_status": "",
    }
    
    final_rows = []
    for row in base_rows:
        key = (row["ocn"], row["colour"])
        cut_data_dict = cut_map.get(key, {})
        fdata = factory_map.get(key, _empty_factory.copy())
        pdata = production_map.get(key, {"sew_quantity": 0, "scan_quantity": 0})
        
        order_qty = float(row.get("order_qty") or 0)
        cut_qty = float(cut_data_dict.get("cut_quantity", 0))
        sew_qty = float(pdata.get("sew_quantity", 0))
        pack_qty = float(fdata.get("pack_quantity", 0))
        ship_qty = float(fdata.get("ship_quantity", 0))
        
        # Set row data
        row.update({
            "cut_quantity": int(cut_qty),
            "last_cut_date": cut_data_dict.get("last_cut_date"),
            "unit": cut_data_dict.get("unit", ""),
            "sew_quantity": sew_qty,
            "sew_balance": int(order_qty - sew_qty),
            "scan_quantity": float(pdata.get("scan_quantity", 0)),
            "pack_quantity": pack_qty,
            "ship_quantity": ship_qty,
            "cut_pct": _pct(cut_qty, order_qty),
            "cut_balance": int(order_qty - cut_qty),
            "pack_balance": int(order_qty - pack_qty),
            "cut_to_pack": _pct(pack_qty, cut_qty),
            "order_to_pack": _pct(pack_qty, order_qty),
            "cut_to_ship": fdata.get("cut_to_ship", 0) or _pct(ship_qty, cut_qty),
            "order_to_ship": fdata.get("order_to_ship", 0) or _pct(ship_qty, order_qty),
            "dispatch_quantity": ship_qty,
            "bal_to_dispatch": int(order_qty - ship_qty)
        })
        
        # CCR Status formatting
        raw_status = row.get("status") or ""
        approval = row.get("custom_consumption_status") or ""
        with_replen = int(cut_data_dict.get("with_replenishment", 0))
        
        if raw_status == "Verified" and not approval:
            display_approval = "Yet to Confirm"
        elif approval == "Approved":
            display_approval = "App with Replenishment" if with_replen else "Approved"
        else:
            display_approval = approval
        row["custom_consumption_status"] = display_approval
        
        # OCR Status
        f_status = fdata.get("factory_status", "")
        ocr_replen = fdata.get("with_replenishment", 0)
        row["ocr_status"] = (
            ("Approved with Replenishment" if ocr_replen == 1 else "Approved")
            if f_status == "Approved" else f_status
        )
        
        # Dead stock
        row["dead_stock"] = dead_stock_map.get(key) if raw_status == "Verified" else None
        
        final_rows.append(row)
    
    # --- 8. Sort ---
    final_rows.sort(key=lambda r: (
        _APPROVAL_PRIORITY.get(r.get("custom_consumption_status", ""), 3),
        r.get("delivery_date") or "",
        r["ocn"],
        r["colour"],
    ))
    
    return final_rows