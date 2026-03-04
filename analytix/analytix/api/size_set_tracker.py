# Copyright (c) 2026, CognitionX and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _


@frappe.whitelist()
def upsert_tracker(ocn, style, colour, fields):
    """
    Find the Size Set Tracker for the given ocn+style+colour and update it.
    If no tracker exists yet, create one first (first-save behaviour).

    Args:
        ocn     (str): Sales Order name
        style   (str): Style value from Sales Order Item
        colour  (str): Colour value from Sales Order Item
        fields  (str): JSON-encoded dict of fieldname→value to set
                       e.g. '{"ppm_date": "2026-03-01"}'

    Returns:
        str: Name of the Size Set Tracker document
    """
    if isinstance(fields, str):
        fields = json.loads(fields)

    tracker_name = frappe.db.get_value(
        "Size Set Tracker",
        {"ocn": ocn, "style": style, "colour": colour},
        "name"
    )

    if tracker_name:
        # Update existing tracker
        doc = frappe.get_doc("Size Set Tracker", tracker_name)
        for fieldname, value in fields.items():
            doc.set(fieldname, value or None)
        doc.save(ignore_permissions=True)
    else:
        # Create tracker on first save
        doc = frappe.get_doc({
            "doctype": "Size Set Tracker",
            "ocn": ocn,
            "style": style,
            "colour": colour,
            **{k: v or None for k, v in fields.items()}
        })
        doc.insert(ignore_permissions=True)
        tracker_name = doc.name

    frappe.db.commit()
    return tracker_name