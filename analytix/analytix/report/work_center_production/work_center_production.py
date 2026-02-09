# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import date

def execute(filters=None):
    filters = frappe._dict(filters or {})

    as_on_date = frappe.utils.getdate(filters.as_on_date or date.today())
    unit = filters.get("unit")  # optional string

    # Fetch production data — ALL history up to as_on_date
    cutting_rows = get_cutting_data(as_on_date, unit)
    sew_fin_rows = get_sewing_finishing_data(as_on_date, unit)

    # Get only OCNs that had activity ON the selected date
    active_ocns = set()
    for row in cutting_rows:
        if row.scan_date == as_on_date:
            active_ocns.add(row.ocn)
    for row in sew_fin_rows:
        if row.scan_date == as_on_date:
            active_ocns.add(row.ocn)

    if not active_ocns:
        return get_columns(), [], f"No production activity found on {as_on_date.strftime('%d %b %Y')}."

    # Fetch base order info for active OCNs only
    order_info = get_sales_order_info(list(active_ocns))
    if not order_info:
        return get_columns(), [], "No matching Sales Orders found."

    # Build summary
    summary = {}
    for ocn_key, styles in order_info.items():
        for style, qty in styles.items():
            key = (ocn_key, style)
            summary[key] = {
                "unit": "-",
                "ocn": ocn_key,
                "style": style,
                "order_quantity": qty,
                "cutting_on_date": 0,
                "cutting_till_date": 0,
                "sewing_on_date": 0,
                "sewing_till_date": 0,
                "finishing_on_date": 0,
                "finishing_till_date": 0
            }

    # Process Cutting - only for active OCNs
    for row in cutting_rows:
        ocn_key = row.ocn
        if ocn_key not in active_ocns:
            continue
            
        style = next(iter(order_info.get(ocn_key, {}).keys()), "")
        key = (ocn_key, style)
        if key in summary:
            summary[key]["unit"] = row.factory_name or "-"
            if row.scan_date == as_on_date:
                summary[key]["cutting_on_date"] += row.cut_quantity
            summary[key]["cutting_till_date"] += row.cut_quantity

    # Process Sewing & Finishing - only for active OCNs
    for row in sew_fin_rows:
        ocn_key = row.ocn
        if ocn_key not in active_ocns:
            continue
            
        style = next(iter(order_info.get(ocn_key, {}).keys()), "")
        key = (ocn_key, style)
        if key in summary:
            summary[key]["unit"] = row.factory_name or "-"
            if row.operation == "Endline QC":
                op_type = "sewing"
            elif row.operation.startswith("Finishing QC"):
                op_type = "finishing"
            else:
                continue

            if row.scan_date == as_on_date:
                if op_type == "sewing":
                    summary[key]["sewing_on_date"] += row.quantity
                elif op_type == "finishing":
                    summary[key]["finishing_on_date"] += row.quantity

            if op_type == "sewing":
                summary[key]["sewing_till_date"] += row.quantity
            elif op_type == "finishing":
                summary[key]["finishing_till_date"] += row.quantity

    data = list(summary.values())
    data.sort(key=lambda x: (x["unit"], x["ocn"], x["style"]))

    message = f"Production report for {as_on_date.strftime('%d %b %Y')} - showing all OCNs with activity"
    return get_columns(), data, message


def get_columns():
    return [
        {"label": "Unit", "fieldname": "unit", "fieldtype": "Data", "width": 120},
        {"label": "OCN", "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 140},
        {"label": "Style", "fieldname": "style", "fieldtype": "Data", "width": 160},
        {"label": "Order Quantity", "fieldname": "order_quantity", "fieldtype": "Int", "width": 140},
        {"label": "Cutting - On Date", "fieldname": "cutting_on_date", "fieldtype": "Int", "width": 150},
        {"label": "Cutting - Till Date", "fieldname": "cutting_till_date", "fieldtype": "Int", "width": 150},
        {"label": "Sewing - On Date", "fieldname": "sewing_on_date", "fieldtype": "Int", "width": 150},
        {"label": "Sewing - Till Date", "fieldname": "sewing_till_date", "fieldtype": "Int", "width": 150},
        {"label": "Finishing - On Date", "fieldname": "finishing_on_date", "fieldtype": "Int", "width": 160},
        {"label": "Finishing - Till Date", "fieldname": "finishing_till_date", "fieldtype": "Int", "width": 160},
    ]


def get_sales_order_info(ocn_list):
    """Fetch style and order qty for given OCN(s)"""
    if not ocn_list:
        return {}
    
    query = """
        SELECT 
            so.name AS ocn,
            soi.custom_style AS style,
            SUM(soi.qty) AS order_qty
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        WHERE so.name IN %(ocn_list)s
        GROUP BY so.name, soi.custom_style
    """
    rows = frappe.db.sql(query, {"ocn_list": ocn_list}, as_dict=True)
    result = {}
    for r in rows:
        if r.ocn not in result:
            result[r.ocn] = {}
        result[r.ocn][r.style] = r.order_qty
    return result


def get_cutting_data(to_date, unit=None):
    conditions = [
        "cci.docstatus = 1",
        "con.docstatus = 1",
        "DATE(con.creation) <= %(to_date)s"
    ]
    values = {
        "to_date": to_date
    }

    if unit:
        conditions.append("fbu.name = %(unit)s")
        values["unit"] = unit

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            cci.sales_order AS ocn,
            fbu.factory_name,
            SUM(cci.confirmed_quantity) AS cut_quantity,
            DATE(con.creation) AS scan_date
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` con 
            ON con.name = cci.parent
        LEFT JOIN `tabFactory Business Unit` fbu 
            ON fbu.name = con.factory_business_unit
        WHERE {where_clause}
        GROUP BY cci.sales_order, fbu.factory_name, DATE(con.creation)
    """
    return frappe.db.sql(query, values, as_dict=True)


def get_sewing_finishing_data(to_date, unit=None):
    conditions = [
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Activated', 'Pass')",
        "DATE(isl.creation) <= %(to_date)s",
        "(isl.operation = 'Endline QC' OR isl.operation LIKE 'Finishing QC%%')"
    ]
    values = {
        "to_date": to_date
    }

    if unit:
        conditions.append("fbu.name = %(unit)s")
        values["unit"] = unit

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT 
            tbc.sales_order AS ocn,
            fbu.factory_name,
            pi.quantity,
            DATE(isl.creation) AS scan_date,
            isl.operation
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi 
            ON pi.name = isl.production_item
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
            ON tbc.name = pi.bundle_configuration
        INNER JOIN `tabCut Kit Plan Bundle Details` ckd 
            ON ckd.production_item_id = pi.name
        INNER JOIN `tabCut Kit Plan` ckp 
            ON ckp.name = ckd.parent
        LEFT JOIN `tabFactory Business Unit` fbu 
            ON fbu.name = ckp.factory_business_unit
        WHERE {where_clause}
    """
    return frappe.db.sql(query, values, as_dict=True)