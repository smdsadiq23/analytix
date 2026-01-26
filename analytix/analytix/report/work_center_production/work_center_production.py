# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt


import frappe
from datetime import date

def execute(filters=None):
    filters = frappe._dict(filters or {})

    as_on_date = frappe.utils.getdate(filters.as_on_date or date.today())
    unit = filters.get("unit")  # optional string
    ocn = filters.get("ocn")    # required string

    if not ocn:
        return get_columns(), [], "Please select an OCN (Sales Order)."

    first_day_year = as_on_date.replace(month=1, day=1)

    # Fetch base order info
    order_info = get_sales_order_info(ocn)
    if not order_info:
        return get_columns(), [], "No matching Sales Order found."

    # Fetch production data
    cutting_rows = get_cutting_data(first_day_year, as_on_date, ocn, unit)
    sew_fin_rows = get_sewing_finishing_data(first_day_year, as_on_date, ocn, unit)

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

    # Process Cutting
    for row in cutting_rows:
        ocn_key = row.ocn
        style = next(iter(order_info.get(ocn_key, {}).keys()), "")
        key = (ocn_key, style)
        if key in summary:
            summary[key]["unit"] = row.factory_name or "-"
            if row.scan_date == as_on_date:
                summary[key]["cutting_on_date"] += row.cut_quantity
            summary[key]["cutting_till_date"] += row.cut_quantity

    # Process Sewing & Finishing
    for row in sew_fin_rows:
        ocn_key = row.ocn
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

    message = f"Report as on {as_on_date.strftime('%d %b %Y')}"
    return get_columns(), data, message


def get_columns():
    return [
        # {"label": "Unit", "fieldname": "unit", "fieldtype": "Data", "width": 180},
        # {"label": "OCN", "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 150},
        {"label": "Style", "fieldname": "style", "fieldtype": "Data", "width": 160},
        {"label": "Order Quantity", "fieldname": "order_quantity", "fieldtype": "Int", "width": 140},
        {"label": "Cutting - On Date", "fieldname": "cutting_on_date", "fieldtype": "Int", "width": 150},
        {"label": "Cutting - Till Date", "fieldname": "cutting_till_date", "fieldtype": "Int", "width": 150},
        {"label": "Sewing - On Date", "fieldname": "sewing_on_date", "fieldtype": "Int", "width": 150},
        {"label": "Sewing - Till Date", "fieldname": "sewing_till_date", "fieldtype": "Int", "width": 150},
        {"label": "Finishing - On Date", "fieldname": "finishing_on_date", "fieldtype": "Int", "width": 160},
        {"label": "Finishing - Till Date", "fieldname": "finishing_till_date", "fieldtype": "Int", "width": 160},
    ]


def get_sales_order_info(ocn):
    """Fetch style and order qty for a single OCN"""
    query = """
        SELECT 
            so.name AS ocn,
            soi.custom_style AS style,
            SUM(soi.qty) AS order_qty
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        WHERE so.name = %(ocn)s
        GROUP BY so.name, soi.custom_style
    """
    rows = frappe.db.sql(query, {"ocn": ocn}, as_dict=True)
    result = {}
    for r in rows:
        if r.ocn not in result:
            result[r.ocn] = {}
        result[r.ocn][r.style] = r.order_qty
    return result


def get_cutting_data(from_date, to_date, ocn, unit=None):
    conditions = [
        "cci.docstatus = 1",
        "con.docstatus = 1",
        "cci.sales_order = %(ocn)s",
        "DATE(con.creation) BETWEEN %(from_date)s AND %(to_date)s"
    ]
    values = {
        "from_date": from_date,
        "to_date": to_date,
        "ocn": ocn
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


def get_sewing_finishing_data(from_date, to_date, ocn, unit=None):
    conditions = [
        "isl.log_status = 'Completed'",
        "isl.status IN ('Counted', 'Activated', 'Pass')",
        "tbc.sales_order = %(ocn)s",
        "DATE(isl.creation) BETWEEN %(from_date)s AND %(to_date)s",
        "(isl.operation = 'Endline QC' OR isl.operation LIKE 'Finishing QC%%')"
    ]
    values = {
        "from_date": from_date,
        "to_date": to_date,
        "ocn": ocn
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