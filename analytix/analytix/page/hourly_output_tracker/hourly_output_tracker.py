# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime, date as _date

# Sections in display order — these map to Physical Cell cell_name values
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

# Time slots — each label is the END of a 1-hour window:
#   "09:00" = scans logged during 08:00-08:59  (first hour: 8 AM to 9 AM)
#   "10:00" = scans logged during 09:00-09:59
#   "11:00" = scans logged during 10:00-10:59
#   "12:00" = scans logged during 11:00-11:59
#   "13:00" = scans logged during 12:00-12:59
#   "15:00" = scans logged during 14:00-14:59  (1 PM lunch skipped in display)
#   "16:00" = scans logged during 15:00-15:59
#   "17:00" = scans logged during 16:00-16:59
#   "18:00" = scans logged during 17:00-17:59
#   "19:00" = scans logged during 18:00-18:59  (last regular slot)
# Overtime  = scans logged during hour >= 19 (7 PM onwards)
TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "15:00", "16:00", "17:00", "18:00", "19:00",
]
OVERTIME_SLOT = "overtime"   # hour >= 19 (7 PM onwards)

# Map: scan hour -> slot label it belongs to
# Each slot covers the hour BEFORE its label time
_HOUR_TO_SLOT = {
    8:  "09:00",
    9:  "10:00",
    10: "11:00",
    11: "12:00",
    12: "13:00",
    13: "15:00",   # 1 PM scans -> show under 2 PM label (post-lunch)
    14: "15:00",
    15: "16:00",
    16: "17:00",
    17: "18:00",
    18: "19:00",
}


@frappe.whitelist()
def get_hourly_data(work_date=None):
    """
    Returns hourly output counts bucketed by time slot and section (Physical Cell).
    Data source: Item Scan Log — grouped by hour(logged_time) and physical_cell.

    Slot logic:
        Each slot label = end of the hour window.
        e.g. "09:00 AM" slot contains scans from 08:00-08:59.
        Overtime = any scan at hour >= 19 (7 PM onwards).

    Args:
        work_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to today.

    Returns:
        dict with keys: date, slots, sections, data, section_totals, targets
    """
    if not work_date:
        work_date = str(_date.today())

    try:
        datetime.strptime(work_date, "%Y-%m-%d")
    except ValueError:
        frappe.throw("Invalid date format. Use YYYY-MM-DD.")

    date_start = work_date + " 00:00:00"
    date_end   = work_date + " 23:59:59"

    rows = frappe.db.sql("""
        SELECT
            pc.cell_name                        AS section,
            HOUR(isl.logged_time)               AS slot_hour,
            COUNT(isl.name)                     AS cnt
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabPhysical Cell` pc ON pc.name = isl.physical_cell
        WHERE isl.logged_time BETWEEN %(date_start)s AND %(date_end)s
          AND isl.log_status = 'Completed'
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link')
          )
          AND pc.cell_name IN %(sections)s
        GROUP BY pc.cell_name, HOUR(isl.logged_time)
        ORDER BY slot_hour
    """, {
        "date_start": date_start,
        "date_end":   date_end,
        "sections":   tuple(SECTIONS) if len(SECTIONS) > 1 else (SECTIONS[0], SECTIONS[0]),
    }, as_dict=True)

    # Initialise data structure
    all_slots = TIME_SLOTS + [OVERTIME_SLOT]
    data = {slot: {sec: 0 for sec in SECTIONS} for slot in all_slots}
    section_totals = {sec: 0 for sec in SECTIONS}

    for row in rows:
        hour    = int(row.slot_hour)
        section = row.section
        if section not in SECTIONS:
            continue
        count = int(row.cnt or 0)

        slot_key = _hour_to_slot(hour)
        data[slot_key][section] = data[slot_key].get(section, 0) + count
        section_totals[section] = section_totals.get(section, 0) + count

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
    # 7 PM (19:00) and beyond -> Overtime
    if hour >= 19:
        return OVERTIME_SLOT
    # Before 8 AM edge case -> first slot
    return "09:00"