# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime, date as _date

# Section display names shown in the UI (Title Case)
SECTIONS = [
    "Knitting",
    "Mending",
    "Washing",
    "Cutting",
    "Linking",
    "Sewing",
    "Production Out",
    "Embroidery",
    "Pressing",
    "Final Checking",
    "Packing",
]

# Uppercase cell_name values as stored in tabPhysical Cell
CELL_NAMES_UPPER = [s.upper() for s in SECTIONS]

# Map DB cell_name (uppercase) -> display name (Title Case)
CELL_TO_DISPLAY = {s.upper(): s for s in SECTIONS}
# Override the ones that differ
CELL_TO_DISPLAY["PRODUCTION OUT"] = "Production Out"
CELL_TO_DISPLAY["FINAL CHECKING"] = "Final Checking"

# Time slots — each label = end of the 1-hour window:
#   "09:00" = scans during 08:00-08:59  (first hour: 8 AM to 9 AM)
#   "10:00" = scans during 09:00-09:59
#   ...
#   "19:00" = scans during 18:00-18:59  (last regular slot)
# Overtime  = scans during hour >= 19 (7 PM onwards)
TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "15:00", "16:00", "17:00", "18:00", "19:00",
]
OVERTIME_SLOT = "overtime"

# Map: scan hour -> slot label it belongs to
_HOUR_TO_SLOT = {
    8:  "09:00",
    9:  "10:00",
    10: "11:00",
    11: "12:00",
    12: "13:00",
    13: "15:00",
    14: "15:00",
    15: "16:00",
    16: "17:00",
    17: "18:00",
    18: "19:00",
}


@frappe.whitelist()
def get_hourly_data(work_date=None):
    """
    Returns hourly output counts bucketed by time slot and section.
    Uses the same joins and filters as the production dashboard so data matches.

    Counts SUM(pi.quantity) grouped by physical cell and hour of logged_time.
    Uses the last_operation per cell (OUT scan) to count completed output.
    """
    if not work_date:
        work_date = str(_date.today())

    try:
        datetime.strptime(work_date, "%Y-%m-%d")
    except ValueError:
        frappe.throw("Invalid date format. Use YYYY-MM-DD.")

    date_start = work_date + " 00:00:00"
    date_end   = work_date + " 23:59:59"

    cell_list = ", ".join([f"'{c}'" for c in CELL_NAMES_UPPER])

    rows = frappe.db.sql(f"""
        SELECT
            pc.cell_name                            AS cell_name,
            HOUR(isl.logged_time)                   AS slot_hour,
            COALESCE(SUM(pi.quantity), 0)           AS qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc                                       ON tbc.parent = tor.name
                                                   AND tbc.size = pi.size
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component
                                                   AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                   ON pcflo.parent = tbc.work_order
                                                   AND pcflo.physical_cell = pc.name
        WHERE isl.logged_time BETWEEN %(date_start)s AND %(date_end)s
          AND isl.log_status = 'Completed'
          AND pc.cell_name IN ({cell_list})
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
          AND isl.operation = CASE
              WHEN pc.cell_name = 'MENDING' THEN 'MENDING OUT'
              ELSE pcflo.last_operation
          END
        GROUP BY pc.cell_name, HOUR(isl.logged_time)
        ORDER BY slot_hour
    """, {
        "date_start": date_start,
        "date_end":   date_end,
    }, as_dict=True)

    # Initialise data structure
    all_slots = TIME_SLOTS + [OVERTIME_SLOT]
    data = {slot: {sec: 0 for sec in SECTIONS} for slot in all_slots}
    section_totals = {sec: 0 for sec in SECTIONS}

    for row in rows:
        hour     = int(row.slot_hour)
        cell     = (row.cell_name or "").upper()
        display  = CELL_TO_DISPLAY.get(cell)
        if not display:
            continue
        qty = int(row.qty or 0)

        slot_key = _hour_to_slot(hour)
        data[slot_key][display] = data[slot_key].get(display, 0) + qty
        section_totals[display] = section_totals.get(display, 0) + qty

    # Targets — all 0 for now
    targets = {sec: 0 for sec in SECTIONS}

    return {
        "date":           work_date,
        "slots":          all_slots,
        "sections":       SECTIONS,
        "data":           data,
        "section_totals": section_totals,
        "targets":        targets,
    }


def _hour_to_slot(hour: int) -> str:
    """Map a logged_time hour (0-23) to its display slot key."""
    if hour in _HOUR_TO_SLOT:
        return _HOUR_TO_SLOT[hour]
    if hour >= 19:
        return OVERTIME_SLOT
    return "09:00"