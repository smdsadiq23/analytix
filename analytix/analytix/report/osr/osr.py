# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, formatdate, cstr
import math

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 120},
        {"label": _("OCN Created Date"), "fieldname": "ocn_created_date", "fieldtype": "Date", "width": 120},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Data", "width": 120},
        {"label": _("Order to Company"), "fieldname": "order_to_company", "fieldtype": "Data", "width": 120},
        {"label": _("Style Ref"), "fieldname": "style_ref", "fieldtype": "Data", "width": 120},
        {"label": _("OCN"), "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 130},
        {"label": _("Order Qty"), "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        {"label": _("IAPL FOB"), "fieldname": "iapl_fob", "fieldtype": "Currency", "width": 100},
        {"label": _("IAPL Margin"), "fieldname": "iapl_margin", "fieldtype": "Currency", "width": 100},
        {"label": _("FOB"), "fieldname": "fob", "fieldtype": "Currency", "width": 100},
        {"label": _("Order Value"), "fieldname": "order_value", "fieldtype": "Currency", "width": 120},
        {"label": _("Fit Order Qty"), "fieldname": "fit_order_qty", "fieldtype": "Int", "width": 120},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 80},
        {"label": _("Cut Qty"), "fieldname": "cut_qty", "fieldtype": "Float", "width": 90},
        {"label": _("Cut %"), "fieldname": "cut_percent", "fieldtype": "Percent", "width": 80},
        {"label": _("Cutting Month"), "fieldname": "cutting_month", "fieldtype": "Data", "width": 120},
        {"label": _("Fit Order Qty Deviation Value"), "fieldname": "fit_deviation_value", "fieldtype": "Currency", "width": 150},
        {"label": _("Deviation Under"), "fieldname": "deviation_under", "fieldtype": "Select", "options": "Fabric\nCutting\nPrinting", "width": 120},
        {"label": _("Shipped Qty"), "fieldname": "shipped_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Shipped Date"), "fieldname": "shipped_date", "fieldtype": "Date", "width": 120},
        {"label": _("Shipment Status"), "fieldname": "shipment_status", "fieldtype": "Data", "width": 120},
        {"label": _("Cut to Ship"), "fieldname": "cut_to_ship_percent", "fieldtype": "Percent", "width": 110},
        {"label": _("Order to Ship"), "fieldname": "order_to_ship_percent", "fieldtype": "Percent", "width": 120},
        {"label": _("OSR Customer Order"), "fieldname": "osr_customer_order", "fieldtype": "Percent", "width": 140},
        {"label": _("Customer Order to Ship Gain/Loss Value"), "fieldname": "gain_loss_value", "fieldtype": "Currency", "width": 180},
        {"label": _("Remarks Sandeep"), "fieldname": "remarks_sandeep", "fieldtype": "Data", "width": 150},
        {"label": _("Remarks Logesh"), "fieldname": "remarks_logesh", "fieldtype": "Data", "width": 150},
        {"label": _("Approved by Muthu"), "fieldname": "approved_by_muthu", "fieldtype": "Data", "width": 150},
    ]

def get_data(filters):
    order_data = get_order_summary()
    cut_data = get_cut_summary_with_date()
    ship_data = get_ship_summary_with_factory_ocr()
    deviation_data = get_deviation_summary()
    manual_data = get_manual_style_data()

    # Build lookup maps with string keys
    cut_map = {
        (str(d.get("style") or ""), str(d.get("sales_order") or "")): {
            "cut_qty": flt(d["cut_qty"]),
            "cutting_month": get_month_label(d["cut_date"]) if d.get("cut_date") else ""
        }
        for d in cut_data
    }

    ship_map = {
        (str(d.get("ocn") or ""), str(d.get("style") or "")): {
            "shipped_qty": flt(d["shipped_qty"]),
            "shipped_date": d.get("shipped_date"),
            "shipment_status": "Approved" if d.get("docstatus") == 1 else ""
        }
        for d in ship_data
    }

    deviation_map = {
        (str(d.get("sales_order") or ""), str(d.get("style") or "")): {
            "deviation_under": d["deviation_under"],
            "fit_deviation_value": flt(d["profit_loss_value"])
        }
        for d in deviation_data
    }

    manual_map = {
        (str(d.get("sales_order") or ""), str(d.get("style") or "")): d
        for d in manual_data
    }

    result = []
    for row in order_data:
        fty_date = row.get("fty_date")
        if not fty_date:
            continue

        # Skip if fty_date is not a valid date string
        if isinstance(fty_date, (list, tuple)):
            continue

        month = get_month_label(fty_date)
        order_qty = flt(row["order_qty"])
        fit_order_qty = math.ceil(order_qty * 1.02)
        fob = flt(row.get("fob")) if row.get("fob") is not None else 0.0

        item_code = str(row.get("item_code") or "")
        style_ref = str(row.get("style_ref") or item_code)
        ocn = str(row.get("ocn") or "")

        cut_info = cut_map.get((item_code, ocn), {"cut_qty": 0.0, "cutting_month": ""})
        ship_info = ship_map.get((ocn, item_code), {
            "shipped_qty": 0.0,
            "shipped_date": None,
            "shipment_status": ""
        })
        dev_info = deviation_map.get((ocn, item_code), {})
        manual_info = manual_map.get((ocn, style_ref), {})

        cut_qty = cut_info["cut_qty"]
        shipped_qty = ship_info["shipped_qty"]
        deviation_under = dev_info.get("deviation_under", "")
        fit_deviation_value = dev_info.get("fit_deviation_value", "")

        cut_percent = (cut_qty / fit_order_qty * 100) if fit_order_qty else 0.0
        cut_to_ship_percent = (shipped_qty / cut_qty * 100) if cut_qty else 0.0
        order_to_ship_percent = (shipped_qty / fit_order_qty * 100) if fit_order_qty else 0.0
        osr_customer_order = (shipped_qty / order_qty * 100) if order_qty else 0.0
        gain_loss_value = (shipped_qty / order_qty * fob) if order_qty else 0.0

        result.append({
            "month": month,
            "ocn_created_date": row.get("ocn_created_date"),
            "customer": cstr(row.get("customer") or ""),
            "order_to_company": "IAPL",
            "style_ref": style_ref,
            "ocn": ocn,
            "order_qty": order_qty,
            "iapl_fob": manual_info.get("iapl_fob") or "",
            "iapl_margin": manual_info.get("iapl_margin") or "",
            "fob": fob or "",
            "order_value": "",
            "fit_order_qty": fit_order_qty,
            "unit": "",
            "cut_qty": cut_qty,
            "cut_percent": flt(cut_percent, 2),
            "cutting_month": cut_info["cutting_month"],
            "fit_deviation_value": fit_deviation_value or "",
            "deviation_under": deviation_under,
            "shipped_qty": shipped_qty,
            "shipped_date": manual_info.get("shipped_date") or ship_info["shipped_date"],
            "shipment_status": manual_info.get("shipment_status") or "",
            "cut_to_ship_percent": flt(cut_to_ship_percent, 2),
            "order_to_ship_percent": flt(order_to_ship_percent, 2),
            "osr_customer_order": flt(osr_customer_order, 2),
            "gain_loss_value": flt(gain_loss_value, 2) if gain_loss_value else "",
            "remarks_sandeep": cstr(manual_info.get("remarks_sandeep") or ""),
            "remarks_logesh": cstr(manual_info.get("remarks_logesh") or ""),
            "approved_by_muthu": cstr(manual_info.get("approved_by_muthu") or ""),
        })

    return result

# --- Data Fetching Functions ---

def get_order_summary():
    return frappe.db.sql("""
        SELECT 
            soi.item_code,
            itm.custom_style_master AS style_ref,
            so.customer,
            soi.parent AS ocn,
            so.transaction_date AS ocn_created_date,
            soi.custom_ex_fty_date AS fty_date,
            SUM(soi.qty) AS order_qty,
            so.custom_fob AS fob
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent AND so.docstatus = 1
        INNER JOIN `tabItem` itm 
            ON soi.item_code = itm.name 
            AND itm.custom_select_master = 'Finished Goods'
        WHERE soi.custom_ex_fty_date IS NOT NULL
        GROUP BY 
            soi.item_code,
            itm.custom_style_master,
            so.customer,
            soi.parent,
            so.transaction_date,
            soi.custom_ex_fty_date,
            so.custom_fob
    """, as_dict=1)

def get_cut_summary_with_date():
    return frappe.db.sql("""
        SELECT 
            cd.style,
            cci.sales_order,
            SUM(cci.confirmed_quantity) AS cut_qty,
            MAX(cc.creation) AS cut_date
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

def get_ship_summary_with_factory_ocr():
    return frappe.db.sql("""
        SELECT
            foc.ocn,
            foci.style,
            SUM(foci.ship_quantity) AS shipped_qty,
            MAX(foc.creation) AS shipped_date,
            foc.docstatus
        FROM `tabFactory OCR` foc
        INNER JOIN `tabFactory OCR Item` foci 
            ON foci.parent = foc.name
        WHERE foc.docstatus IN (0, 1)
          AND foc.ocn IS NOT NULL
          AND foci.style IS NOT NULL
        GROUP BY foc.ocn, foci.style
    """, as_dict=1)

def get_deviation_summary():
    return frappe.db.sql("""
        SELECT
            cc.sales_order,
            cc.style,
            cc.profit_loss_value,
            cc.deviation_under
        FROM `tabCan Cut` cc
        WHERE cc.sales_order IS NOT NULL
          AND cc.style IS NOT NULL
          AND cc.deviation_under IS NOT NULL
    """, as_dict=1)

def get_manual_style_data():
    return frappe.db.sql("""
        SELECT
            sales_order,
            style,
            iapl_fob,
            iapl_margin,
            shipped_date,
            shipment_status,
            remarks_sandeep,
            remarks_logesh,
            approved_by_muthu
        FROM `tabOrder Style Tracker`
        WHERE sales_order IS NOT NULL AND style IS NOT NULL
    """, as_dict=1)

def get_month_label(date):
    return formatdate(date, "MMM yyyy")