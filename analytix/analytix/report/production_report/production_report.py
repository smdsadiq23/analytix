# Copyright (c) 2026 Your Company.
# Production Report - Cutting from Cut Confirmation, Sew/Fin from Scan Log

import frappe
from datetime import date

def execute(filters=None):
    as_on_date_str = filters.get("as_on_date") if filters else None
    if as_on_date_str:
        as_on_date = frappe.utils.getdate(as_on_date_str)
    else:
        as_on_date = date.today()

    first_day_month = as_on_date.replace(day=1)
    first_day_year = as_on_date.replace(month=1, day=1)

    # Fetch cutting data (from Cut Confirmation)
    cutting_rows = get_cutting_data(from_date=first_day_year, to_date=as_on_date)
    
    # Fetch sewing & finishing (from Item Scan Log)
    sew_fin_rows = get_sewing_finishing_data(from_date=first_day_year, to_date=as_on_date)

    unit_summary = {}

    # Process Cutting
    for row in cutting_rows:
        factory_name = row.factory_name
        qty = row.cut_quantity or 0
        scan_date = row.last_cut_date  # already a date

        if not factory_name or not scan_date:
            continue

        if factory_name not in unit_summary:
            unit_summary[factory_name] = {
                "unit": factory_name,
                "cutting_on_date": 0, "cutting_mtd": 0, "cutting_ytd": 0,
                "sewing_on_date": 0, "sewing_mtd": 0, "sewing_ytd": 0,
                "finishing_on_date": 0, "finishing_mtd": 0, "finishing_ytd": 0
            }

        if scan_date == as_on_date:
            unit_summary[factory_name]["cutting_on_date"] += qty
        if first_day_month <= scan_date <= as_on_date:
            unit_summary[factory_name]["cutting_mtd"] += qty
        if first_day_year <= scan_date <= as_on_date:
            unit_summary[factory_name]["cutting_ytd"] += qty

    # Process Sewing & Finishing
    for row in sew_fin_rows:
        operation = row.operation
        qty = row.quantity or 0
        scan_date = row.scan_date

        if operation == "Endline QC":
            op_type = "sewing"
            factory_name = row.factory_name
        elif operation.startswith("Finishing QC"):
            op_type = "finishing"
            factory_name = row.factory_name
        else:
            continue

        if not factory_name or not scan_date:
            continue

        if factory_name not in unit_summary:
            unit_summary[factory_name] = {
                "unit": factory_name,
                "cutting_on_date": 0, "cutting_mtd": 0, "cutting_ytd": 0,
                "sewing_on_date": 0, "sewing_mtd": 0, "sewing_ytd": 0,
                "finishing_on_date": 0, "finishing_mtd": 0, "finishing_ytd": 0
            }

        if scan_date == as_on_date:
            if op_type == "sewing":
                unit_summary[factory_name]["sewing_on_date"] += qty
            elif op_type == "finishing":
                unit_summary[factory_name]["finishing_on_date"] += qty

        if first_day_month <= scan_date <= as_on_date:
            if op_type == "sewing":
                unit_summary[factory_name]["sewing_mtd"] += qty
            elif op_type == "finishing":
                unit_summary[factory_name]["finishing_mtd"] += qty

        if first_day_year <= scan_date <= as_on_date:
            if op_type == "sewing":
                unit_summary[factory_name]["sewing_ytd"] += qty
            elif op_type == "finishing":
                unit_summary[factory_name]["finishing_ytd"] += qty

    report_date = as_on_date.strftime("%d %b %Y")
    message = f"Report as on {report_date}"

    sorted_data = sorted(unit_summary.values(), key=lambda x: x['unit'])
    return get_columns(), sorted_data, message


def get_columns():
    return [
        {"label": "Unit", "fieldname": "unit", "fieldtype": "Data", "width": 200},
        {"label": "Cutting - On Date", "fieldname": "cutting_on_date", "fieldtype": "Int", "width": 150},
        {"label": "Cutting - MTD", "fieldname": "cutting_mtd", "fieldtype": "Int", "width": 125},
        {"label": "Cutting - YTD", "fieldname": "cutting_ytd", "fieldtype": "Int", "width": 125},
        {"label": "Sewing - On Date", "fieldname": "sewing_on_date", "fieldtype": "Int", "width": 150},
        {"label": "Sewing - MTD", "fieldname": "sewing_mtd", "fieldtype": "Int", "width": 135},
        {"label": "Sewing - YTD", "fieldname": "sewing_ytd", "fieldtype": "Int", "width": 135},
        {"label": "Finishing - On Date", "fieldname": "finishing_on_date", "fieldtype": "Int", "width": 160},
        {"label": "Finishing - MTD", "fieldname": "finishing_mtd", "fieldtype": "Int", "width": 140},
        {"label": "Finishing - YTD", "fieldname": "finishing_ytd", "fieldtype": "Int", "width": 140},
    ]


def get_cutting_data(from_date, to_date):
    """
    Fetch cutting quantities from Cut Confirmation
    """
    query = """
        SELECT
            fbu.factory_name,
            SUM(cci.confirmed_quantity) AS cut_quantity,
            DATE(con.creation) AS last_cut_date
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` con 
            ON con.name = cci.parent
        LEFT JOIN `tabFactory Business Unit` fbu 
            ON fbu.name = con.factory_business_unit
        WHERE 
            cci.docstatus = 1
            AND con.docstatus = 1
            AND DATE(con.creation) BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY fbu.factory_name, DATE(con.creation)
    """
    return frappe.db.sql(query, {
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)


def get_sewing_finishing_data(from_date, to_date):
    """
    Fetch sewing and finishing from Item Scan Log
    """
    query = """
        SELECT 
            pi.name AS production_item,
            isl.operation,
            COALESCE(pi.quantity, 0) AS quantity,
            DATE(isl.creation) AS scan_date,
            fbu.factory_name
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi 
            ON pi.name = isl.production_item
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabCut Kit Plan Bundle Details` ckd 
            ON ckd.production_item_id = pi.name
        INNER JOIN `tabCut Kit Plan` ckp 
            ON ckp.name = ckd.parent
        LEFT JOIN `tabFactory Business Unit` fbu 
            ON fbu.name = ckp.factory_business_unit
        WHERE 
            isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
            AND (
                isl.operation = 'Endline QC'
                OR isl.operation LIKE 'Finishing QC%%'
            )
            AND DATE(isl.creation) BETWEEN %(from_date)s AND %(to_date)s
    """
    return frappe.db.sql(query, {
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)


def get_filters():
    return [
        {
            "fieldname": "as_on_date",
            "label": "As On Date",
            "fieldtype": "Date",
            "default": frappe.utils.today(),
            "reqd": 1
        }
    ]