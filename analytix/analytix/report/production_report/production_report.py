# Copyright (c) 2026 Your Company.
# Production Report - With As On Date Filter and Factory Names

import frappe
from datetime import date

def execute(filters=None):
    # Get "as_on_date" from filters; default to today
    as_on_date_str = filters.get("as_on_date") if filters else None
    if as_on_date_str:
        as_on_date = frappe.utils.getdate(as_on_date_str)
    else:
        as_on_date = date.today()

    first_day_month = as_on_date.replace(day=1)
    first_day_year = as_on_date.replace(month=1, day=1)

    rows = get_scan_log_data(from_date=first_day_year, to_date=as_on_date)

    unit_summary = {}

    for row in rows:
        operation = row.operation
        qty = row.quantity or 0
        scan_date = row.scan_date

        if operation == "Endline QC":
            op_type = "sewing"
            factory_name = row.ckp_factory_name
        elif operation.startswith("Cutting Outgoing"):
            op_type = "cutting"
            factory_name = row.cd_factory_name
        elif operation.startswith("Finishing QC"):
            op_type = "finishing"
            factory_name = row.ckp_factory_name
        else:
            continue

        if not factory_name:
            continue

        if factory_name not in unit_summary:
            unit_summary[factory_name] = {
                "unit": factory_name,
                "cutting_on_date": 0, "cutting_mtd": 0, "cutting_ytd": 0,
                "sewing_on_date": 0, "sewing_mtd": 0, "sewing_ytd": 0,
                "finishing_on_date": 0, "finishing_mtd": 0, "finishing_ytd": 0
            }

        # On Date
        if scan_date == as_on_date:
            if op_type == "cutting":
                unit_summary[factory_name]["cutting_on_date"] += qty
            elif op_type == "sewing":
                unit_summary[factory_name]["sewing_on_date"] += qty
            elif op_type == "finishing":
                unit_summary[factory_name]["finishing_on_date"] += qty

        # MTD
        if first_day_month <= scan_date <= as_on_date:
            if op_type == "cutting":
                unit_summary[factory_name]["cutting_mtd"] += qty
            elif op_type == "sewing":
                unit_summary[factory_name]["sewing_mtd"] += qty
            elif op_type == "finishing":
                unit_summary[factory_name]["finishing_mtd"] += qty

        # YTD
        if first_day_year <= scan_date <= as_on_date:
            if op_type == "cutting":
                unit_summary[factory_name]["cutting_ytd"] += qty
            elif op_type == "sewing":
                unit_summary[factory_name]["sewing_ytd"] += qty
            elif op_type == "finishing":
                unit_summary[factory_name]["finishing_ytd"] += qty

    report_date = as_on_date.strftime("%d %b %Y")
    message = f"Report as on {report_date}"

    # Sort by factory name
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


def get_scan_log_data(from_date, to_date):
    query = """
        SELECT 
            pi.name AS production_item,
            isl.operation,
            COALESCE(pi.quantity, 0) AS quantity,
            DATE(isl.creation) AS scan_date,
            f1.factory_name AS ckp_factory_name,
            f2.factory_name AS cd_factory_name
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi 
            ON pi.name = isl.production_item
        INNER JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabCut Kit Plan Bundle Details` ckd 
            ON ckd.production_item_id = pi.name
        INNER JOIN `tabCut Kit Plan` ckp 
            ON ckp.name = ckd.parent
        LEFT JOIN `tabBundle Creation` bc 
            ON bc.name = ckp.cut_bundle_order
        LEFT JOIN `tabCut Docket` cd 
            ON cd.name = bc.cut_docket_id
        LEFT JOIN `tabFactory Business Unit` f1 
            ON f1.name = ckp.factory_business_unit
        LEFT JOIN `tabFactory Business Unit` f2 
            ON f2.name = cd.factory_business_unit
        WHERE 
            isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Activated', 'Pass')
            AND (
                isl.operation = 'Endline QC'
                OR isl.operation LIKE 'Cutting Outgoing%%'
                OR isl.operation LIKE 'Finishing QC%%'
            )
            AND DATE(isl.creation) BETWEEN %(from_date)s AND %(to_date)s
    """
    return frappe.db.sql(query, {
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)