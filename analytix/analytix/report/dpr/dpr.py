# Copyright (c) 2025, Cognitonx Logic India Private limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("OCN"), "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": _("Style"), "fieldname": "style", "fieldtype": "Data", "width": 120},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 100},
        {"label": _("Colour"), "fieldname": "colour", "fieldtype": "Data", "width": 120},
        {"label": _("Order Qty"), "fieldname": "order_qty", "fieldtype": "Int", "width": 100},
        {"label": _("Cut Qty"), "fieldname": "cut_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Cut %"), "fieldname": "cut_pct", "fieldtype": "Percent", "width": 100, "precision": 1},
        {"label": _("Cut Balance"), "fieldname": "cut_balance", "fieldtype": "Int", "width": 120},
        {"label": _("Last Cut Date"), "fieldname": "last_cut_date", "fieldtype": "Date", "width": 120},
        {"label": _("CCR Status"), "fieldname": "customer_approval", "fieldtype": "Data", "width": 140},
        {"label": _("Sew Qty"), "fieldname": "sew_quantity", "fieldtype": "Float", "width": 100},
        {"label": _("Sew Balance"), "fieldname": "sew_balance", "fieldtype": "Int", "width": 120},
        {"label": _("Scan Qty"), "fieldname": "scan_quantity", "fieldtype": "Float", "width": 100},
        {"label": _("Pack Qty"), "fieldname": "pack_quantity", "fieldtype": "Float", "width": 100},
        {"label": _("Pack Balance"), "fieldname": "pack_balance", "fieldtype": "Int", "width": 120},
        {"label": _("Ship Qty"), "fieldname": "ship_quantity", "fieldtype": "Float", "width": 100},
        {"label": _("Cut to Pack %"), "fieldname": "cut_to_pack", "fieldtype": "Percent", "width": 120, "precision": 1},
        {"label": _("Order to Pack %"), "fieldname": "order_to_pack", "fieldtype": "Percent", "width": 120, "precision": 1},        
        {"label": _("OCR Status"), "fieldname": "ocr_status", "fieldtype": "Data", "width": 200},
        {"label": _("Dispatch Qty"), "fieldname": "dispatch_quantity", "fieldtype": "Float", "width": 120},
        {"label": _("Bal to Dispatch"), "fieldname": "bal_to_dispatch", "fieldtype": "Int", "width": 120},
        {"label": _("Dead Stock"), "fieldname": "dead_stock", "fieldtype": "Int", "width": 100},
    ]


# Approval values that are considered "Approved" (shown at bottom / hidden by default)
APPROVED_STATUSES = {"Approved", "App with Replenishment"}


def get_data(filters):
    # Build WHERE conditions
    where_conditions = ["so.docstatus = 1"]
    params = {}

    where_clause = " AND ".join(where_conditions)

    # Main query - Sales Order base with aggregated data
    query = f"""
        SELECT
            so.name AS ocn,
            item.custom_style_master AS style,
            fbu.factory_name AS unit,
            sod.custom_color AS colour,
            SUM(sod.custom_order_qty) AS order_qty,
            so.custom_approval AS customer_approval,
            so.custom_consumption_status AS status,
            so.delivery_date
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` sod ON sod.parent = so.name
        INNER JOIN `tabItem` item ON item.name = sod.item_code
        INNER JOIN `tabFactory Business Unit` fbu ON fbu.name = so.custom_fbu
        WHERE {where_clause}
        GROUP BY so.name, item.custom_style_master, sod.custom_color
        ORDER BY so.delivery_date, so.name, sod.custom_color
    """
    
    base_rows = frappe.db.sql(query, params, as_dict=1)

    if not base_rows:
        return []

    # Get OCN list for subsequent queries
    ocn_list = list(set([r["ocn"] for r in base_rows]))
    
    if not ocn_list:
        return []

    # Get Can Cut data for with_replenishment flag
    can_cut_query = """
        SELECT
            cc.sales_order AS ocn,
            cc.colour AS colour,
            cc.with_replenishment
        FROM `tabCan Cut` cc
        WHERE cc.sales_order IN %(ocn_list)s
    """
    
    can_cut_rows = frappe.db.sql(can_cut_query, {"ocn_list": tuple(ocn_list)}, as_dict=1)
    
    # Create a map for with_replenishment: (ocn, colour) -> with_replenishment
    replenishment_map = {}
    for cc in can_cut_rows:
        key = (cc["ocn"], cc["colour"])
        replenishment_map[key] = int(cc.get("with_replenishment") or 0)

    # Get cut quantities and last cut date by OCN and colour
    cut_query = """
        SELECT
            cci.sales_order AS ocn,
            cd.color AS colour,
            SUM(cci.confirmed_quantity) AS cut_quantity,
            MAX(con.creation) AS last_cut_date
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` con ON con.name = cci.parent
        INNER JOIN `tabCut Docket` cd ON cd.name = con.cut_po_number
        WHERE cci.docstatus = 1
          AND con.docstatus = 1
          AND cci.sales_order IN %(ocn_list)s
        GROUP BY cci.sales_order, cd.color
    """
    
    cut_rows = frappe.db.sql(cut_query, {"ocn_list": tuple(ocn_list)}, as_dict=1)
    
    # Create a map for quick lookup: (ocn, colour) -> cut data
    cut_map = {}
    for c in cut_rows:
        key = (c["ocn"], c["colour"])
        cut_map[key] = {
            "cut_quantity": int(c.get("cut_quantity") or 0),
            "last_cut_date": c.get("last_cut_date")
        }

    # Get Factory OCR data (scan, pack, ship quantities)
    factory_ocr_query = """
        SELECT
            fo.ocn AS ocn,
            foi.colour AS colour,
            foi.scan_quantity,
            foi.pack_quantity,
            foi.ship_quantity,
            foi.cut_to_ship,
            foi.order_to_ship,
            fo.with_replenishment,
            fo.status AS factory_status
        FROM `tabFactory OCR` fo
        INNER JOIN `tabFactory OCR Item` foi
            ON foi.parent = fo.name
            AND foi.parenttype = 'Factory OCR'
            AND foi.parentfield = 'table_ocn_details'
        WHERE fo.status = 'Approved'
          AND fo.docstatus < 2
          AND fo.ocn IN %(ocn_list)s
    """
    
    factory_ocr_rows = frappe.db.sql(factory_ocr_query, {"ocn_list": tuple(ocn_list)}, as_dict=1)
    
    # Create a map for Factory OCR data: (ocn, colour) -> factory data
    factory_map = {}
    for f in factory_ocr_rows:
        key = (f["ocn"], f["colour"])
        factory_map[key] = {
            "scan_quantity": float(f.get("scan_quantity") or 0),
            "pack_quantity": float(f.get("pack_quantity") or 0),
            "ship_quantity": float(f.get("ship_quantity") or 0),
            "cut_to_ship": float(f.get("cut_to_ship") or 0),
            "order_to_ship": float(f.get("order_to_ship") or 0),
            "with_replenishment": int(f.get("with_replenishment") or 0),
            "factory_status": f.get("factory_status") or ""
        }

    # Get Sew Qty data (operation='Sewing Incoming%')
    sew_qty_query = """
        SELECT 
            itm.custom_style_master AS style,
            itm.custom_colour_name AS colour,
            tbc.sales_order AS ocn,
            COALESCE(SUM(pi.quantity), 0) AS sew_qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor
            ON tor.name = tbc.parent
            AND tor.item IS NOT NULL
        INNER JOIN `tabItem` itm
            ON itm.name = tor.item
        INNER JOIN `tabProduction Item` pi
            ON pi.tracking_order = tor.name
            AND pi.bundle_configuration = tbc.name
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabItem Scan Log` isl
            ON isl.production_item = pi.name
            AND isl.operation LIKE 'Sewing Incoming%%'
            AND isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
        WHERE tbc.sales_order IN %(ocn_list)s
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.sales_order
    """
    
    sew_qty_rows = frappe.db.sql(sew_qty_query, {"ocn_list": tuple(ocn_list)}, as_dict=1)
    
    # Create a map for Sew Qty: (ocn, colour) -> sew_qty
    sew_qty_map = {}
    for s in sew_qty_rows:
        key = (s["ocn"], s["colour"])
        sew_qty_map[key] = float(s.get("sew_qty") or 0)

    # Get Scan Qty data (operation=tor.last_operation)
    scan_qty_query = """
        SELECT 
            itm.custom_style_master AS style,
            itm.custom_colour_name AS colour,
            tbc.sales_order AS ocn,
            COALESCE(SUM(pi.quantity), 0) AS sew_qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order` tor
            ON tor.name = tbc.parent
            AND tor.item IS NOT NULL
        INNER JOIN `tabItem` itm
            ON itm.name = tor.item
        INNER JOIN `tabProduction Item` pi
            ON pi.tracking_order = tor.name
            AND pi.bundle_configuration = tbc.name
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
		INNER JOIN `tabCut Kit Plan Bundle Details` ckpbd 
		     ON ckpbd.`production_item_id` = pi.name
		 INNER JOIN `tabCut Kit Plan` ckp
		     ON ckp.`name` = ckpbd.parent                 
        INNER JOIN `tabItem Scan Log` isl
            ON isl.production_item = pi.name
            AND isl.operation = ckp.last_operation
            AND isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
        WHERE tbc.sales_order IN %(ocn_list)s
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.sales_order
    """
    
    scan_qty_rows = frappe.db.sql(scan_qty_query, {"ocn_list": tuple(ocn_list)}, as_dict=1)
    
    # Create a map for Scan Qty: (ocn, colour) -> scan_qty
    scan_qty_map = {}
    for s in scan_qty_rows:
        key = (s["ocn"], s["colour"])
        scan_qty_map[key] = float(s.get("scan_qty") or 0)

    # Get Dead Stock data (balance_as_per_lay_record for Verified status)
    # GRN received quantity
    grn_query = """
        SELECT
            grn.ocn AS ocn,
            gri.color AS colour,
            SUM(gri.received_quantity) AS received_qty
        FROM `tabGoods Receipt Note` grn
        INNER JOIN `tabGoods Receipt Item` gri ON gri.parent = grn.name
        INNER JOIN `tabSales Order` so ON so.name = grn.ocn
        WHERE grn.docstatus = 1
          AND so.custom_consumption_status = 'Verified'
          AND grn.ocn IN %(ocn_list)s
        GROUP BY grn.ocn, gri.color
    """
    
    grn_rows = frappe.db.sql(grn_query, {"ocn_list": tuple(ocn_list)}, as_dict=1)
    grn_map = {(r["ocn"], r["colour"]): float(r.get("received_qty") or 0) for r in grn_rows}
    
    # Lay actual total
    lay_query = """
        SELECT
            clr.ocn AS ocn,
            clr.colour AS colour,
            SUM(lrd.actual_total) AS lay_actual_total
        FROM `tabCutting Lay Record` clr
        INNER JOIN `tabLay Roll Details` lrd ON lrd.parent = clr.name
        INNER JOIN `tabSales Order` so ON so.name = clr.ocn
        WHERE clr.docstatus = 1
          AND so.custom_consumption_status = 'Verified'
          AND clr.ocn IN %(ocn_list)s
        GROUP BY clr.ocn, clr.colour
    """
    
    lay_rows = frappe.db.sql(lay_query, {"ocn_list": tuple(ocn_list)}, as_dict=1)
    lay_map = {(r["ocn"], r["colour"]): float(r.get("lay_actual_total") or 0) for r in lay_rows}

    # Merge cut data into base rows and calculate derived fields
    final_rows = []
    for row in base_rows:
        key = (row["ocn"], row["colour"])
        cut_data = cut_map.get(key, {"cut_quantity": 0, "last_cut_date": None})
        factory_data = factory_map.get(key, {
            "scan_quantity": 0,
            "pack_quantity": 0,
            "ship_quantity": 0,
            "cut_to_ship": 0,
            "order_to_ship": 0,
            "with_replenishment": 0,
            "factory_status": ""
        })
        
        row["cut_quantity"] = cut_data["cut_quantity"]
        row["last_cut_date"] = cut_data["last_cut_date"]
        
        # Factory OCR fields (pack and ship only)
        row["pack_quantity"] = factory_data["pack_quantity"]
        row["ship_quantity"] = factory_data["ship_quantity"]
        
        # Calculate cut % and cut balance
        order_qty = float(row.get("order_qty") or 0)
        cut_qty = float(row.get("cut_quantity") or 0)
        pack_qty = float(row.get("pack_quantity") or 0)
        ship_qty = float(row.get("ship_quantity") or 0)
        
        # Sew Qty and Sew Balance
        sew_qty = sew_qty_map.get(key, 0)
        row["sew_quantity"] = float(sew_qty)
        row["sew_balance"] = int(order_qty - sew_qty)
        
        # Scan Qty (from query instead of Factory OCR)
        scan_qty = scan_qty_map.get(key, 0)
        row["scan_quantity"] = float(scan_qty)
        
        if order_qty > 0:
            row["cut_pct"] = (cut_qty / order_qty) * 100.0
        else:
            row["cut_pct"] = 0.0
        
        row["cut_balance"] = int(order_qty - cut_qty)
        
        # Pack balance
        row["pack_balance"] = int(order_qty - pack_qty)
        
        # Cut to Pack % and Order to Pack %
        if cut_qty > 0:
            row["cut_to_pack"] = (pack_qty / cut_qty) * 100.0
        else:
            row["cut_to_pack"] = 0.0
        
        if order_qty > 0:
            row["order_to_pack"] = (pack_qty / order_qty) * 100.0
        else:
            row["order_to_pack"] = 0.0
        
        # Cut to Ship % and Order to Ship % (from Factory OCR or calculate)
        cut_to_ship = factory_data.get("cut_to_ship")
        if cut_to_ship is None or cut_to_ship == 0:
            cut_to_ship = (ship_qty / cut_qty * 100) if cut_qty > 0 else 0
        row["cut_to_ship"] = float(cut_to_ship)
        
        order_to_ship = factory_data.get("order_to_ship")
        if order_to_ship is None or order_to_ship == 0:
            order_to_ship = (ship_qty / order_qty * 100) if order_qty > 0 else 0
        row["order_to_ship"] = float(order_to_ship)
        
        # Apply customer approval display logic
        current_approval = row.get("customer_approval") or ""
        row_status = row.get("status") or ""
        with_replenishment = replenishment_map.get(key, 0)
        
        display_approval = current_approval
        
        if row_status == "Verified" and not current_approval:
            display_approval = "Yet to Confirm"
        elif current_approval == "Approved":
            display_approval = "App with Replenishment" if with_replenishment else "Approved"
        
        row["customer_approval"] = display_approval
        
        # Dispatch Qty = Ship Qty from Factory OCR
        row["dispatch_quantity"] = ship_qty
        
        # Bal to Dispatch = Order - Ship
        row["bal_to_dispatch"] = int(order_qty - ship_qty)
        
        # Dead Stock = received_qty - lay_actual_total (only for Verified status)
        row_status = row.get("status") or ""
        if row_status == "Verified":
            received_qty = grn_map.get(key, 0)
            lay_actual_total = lay_map.get(key, 0)
            row["dead_stock"] = float(received_qty - lay_actual_total)
        else:
            row["dead_stock"] = None
        
        # OCR Status logic
        factory_status = factory_data.get("factory_status") or ""
        ocr_with_replenishment = factory_data.get("with_replenishment") or 0
        
        if factory_status == "Approved":
            row["ocr_status"] = "Approved with Replenishment" if ocr_with_replenishment == 1 else "Approved"
        else:
            row["ocr_status"] = factory_status
        
        final_rows.append(row)

    # --- Filter: hide Approved records by default unless show_approved is checked ---
    show_approved = filters.get("show_approved")
    if not show_approved:
        final_rows = [r for r in final_rows if r.get("customer_approval") not in APPROVED_STATUSES]

    # --- Sort: pending records first, approved records at the bottom ---
    def get_approval_priority(approval):
        if approval == "Yet to Confirm":
            return 0
        elif approval in ("", None):
            return 1          # blank / unknown — still pending, show near top
        elif approval == "App with Replenishment":
            return 2          # approved variant — pushed to bottom
        elif approval == "Approved":
            return 3          # fully approved — very bottom
        else:
            return 1          # any other value treated as pending

    # Sort by approval priority first, then by delivery_date, OCN, colour for stability
    final_rows.sort(
        key=lambda row: (
            get_approval_priority(row.get("customer_approval", "")),
            row.get("delivery_date") or "",
            row["ocn"],
            row["colour"]
        )
    )    

    return final_rows