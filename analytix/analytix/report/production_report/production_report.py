# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import date

def execute(filters=None):
    today = date.today()
    first_day_month = today.replace(day=1)
    first_day_year = today.replace(month=1, day=1)

    # Fetch all relevant scan logs in one go
    rows = get_scan_log_data(from_date=first_day_year, to_date=today)

    unit_summary = {}

    for row in rows:
        operation = row.operation
        qty = row.quantity or 0
        scan_date = row.scan_date

        # Classify operation
        if operation == "Endline QC":
            op_type = "sewing"
            unit = row.ckp_fbu  # From Cut Kit Plan
        elif operation.startswith("Cutting Outgoing"):
            op_type = "cutting"
            unit = row.cd_fbu   # From Cut Docket
        elif operation.startswith("Finishing QC"):
            op_type = "finishing"
            unit = row.ckp_fbu  # From Cut Kit Plan
        else:
            continue  # Skip unknown operations

        if not unit:
            continue  # Skip if unit is missing

        # Initialize unit entry if not exists
        if unit not in unit_summary:
            unit_summary[unit] = {
                "unit": unit,
                "cutting_on_date": 0, "cutting_mtd": 0, "cutting_ytd": 0,
                "sewing_on_date": 0, "sewing_mtd": 0, "sewing_ytd": 0,
                "finishing_on_date": 0, "finishing_mtd": 0, "finishing_ytd": 0
            }

        # On Date (today only)
        if scan_date == today:
            if op_type == "cutting":
                unit_summary[unit]["cutting_on_date"] += qty
            elif op_type == "sewing":
                unit_summary[unit]["sewing_on_date"] += qty
            elif op_type == "finishing":
                unit_summary[unit]["finishing_on_date"] += qty

        # Month-to-Date
        if scan_date >= first_day_month:
            if op_type == "cutting":
                unit_summary[unit]["cutting_mtd"] += qty
            elif op_type == "sewing":
                unit_summary[unit]["sewing_mtd"] += qty
            elif op_type == "finishing":
                unit_summary[unit]["finishing_mtd"] += qty

        # Year-to-Date (all rows are within YTD due to query filter)
        if op_type == "cutting":
            unit_summary[unit]["cutting_ytd"] += qty
        elif op_type == "sewing":
            unit_summary[unit]["sewing_ytd"] += qty
        elif op_type == "finishing":
            unit_summary[unit]["finishing_ytd"] += qty

    return get_columns(), list(unit_summary.values())


def get_columns():
    return [
        {"label": "Unit", "fieldname": "unit", "fieldtype": "Data", "width": 150},
        {"label": "Cutting - On Date", "fieldname": "cutting_on_date", "fieldtype": "Int", "width": 120},
        {"label": "Cutting - MTD", "fieldname": "cutting_mtd", "fieldtype": "Int", "width": 100},
        {"label": "Cutting - YTD", "fieldname": "cutting_ytd", "fieldtype": "Int", "width": 100},
        {"label": "Sewing - On Date", "fieldname": "sewing_on_date", "fieldtype": "Int", "width": 120},
        {"label": "Sewing - MTD", "fieldname": "sewing_mtd", "fieldtype": "Int", "width": 100},
        {"label": "Sewing - YTD", "fieldname": "sewing_ytd", "fieldtype": "Int", "width": 100},
        {"label": "Finishing - On Date", "fieldname": "finishing_on_date", "fieldtype": "Int", "width": 120},
        {"label": "Finishing - MTD", "fieldname": "finishing_mtd", "fieldtype": "Int", "width": 100},
        {"label": "Finishing - YTD", "fieldname": "finishing_ytd", "fieldtype": "Int", "width": 100},
    ]


def get_scan_log_data(from_date, to_date):
    """
    Fetch all relevant Item Scan Log entries with FBU from both paths.
    """
    query = """
        SELECT 
            pi.name AS production_item,
            isl.operation,
            COALESCE(pi.quantity, 0) AS quantity,
            DATE(isl.creation) AS scan_date,
            ckp.factory_business_unit AS ckp_fbu,
            cd.factory_business_unit AS cd_fbu
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