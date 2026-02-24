# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}

    columns = [
        {"label": "SL#", "fieldname": "sl_no", "fieldtype": "Int", "width": 60},
        {"label": "OCN", "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 130},
        {"label": "Style", "fieldname": "style", "fieldtype": "Data", "width": 140},
        {"label": "Color", "fieldname": "colour", "fieldtype": "Data", "width": 110},
        {"label": "Order qty", "fieldname": "order_quantity", "fieldtype": "Float", "width": 110},
        {"label": "Cut Qty", "fieldname": "cut_quantity", "fieldtype": "Float", "width": 90},
        {"label": "Scan qty", "fieldname": "scan_quantity", "fieldtype": "Float", "width": 90},
        {"label": "Pack qty", "fieldname": "pack_quantity", "fieldtype": "Float", "width": 90},
        {"label": "Ship qty", "fieldname": "ship_quantity", "fieldtype": "Float", "width": 90},
        {"label": "Good Garments", "fieldname": "good_garments", "fieldtype": "Float", "width": 120},
        {"label": "Reject Garments", "fieldname": "rejected_garments", "fieldtype": "Float", "width": 130},
        {"label": "Rejected panels", "fieldname": "rejected_panels", "fieldtype": "Float", "width": 130},
        {"label": "Difference", "fieldname": "difference", "fieldtype": "Float", "width": 100},
        {"label": "Cut to ship%", "fieldname": "cut_to_ship", "fieldtype": "Percent", "width": 110},
        {"label": "Order to Ship", "fieldname": "order_to_ship", "fieldtype": "Percent", "width": 110},
        {"label": "Status", "fieldname": "status_text", "fieldtype": "Data", "width": 220},
    ]

    rows = frappe.db.sql(
        """
        SELECT
            fo.name AS factory_ocr,
            fo.ocn AS ocn,
            fo.with_replenishment AS with_replenishment,

            foi.style AS style,
            foi.colour AS colour,
            foi.order_quantity AS order_quantity,
            foi.cut_quantity AS cut_quantity,
            foi.scan_quantity AS scan_quantity,
            foi.pack_quantity AS pack_quantity,
            foi.ship_quantity AS ship_quantity,
            foi.good_garments AS good_garments,
            foi.rejected_garments AS rejected_garments,
            foi.rejected_panels AS rejected_panels,
            foi.cut_to_ship_diff AS cut_to_ship_diff,
            foi.cut_to_ship AS cut_to_ship,
            foi.order_to_ship AS order_to_ship,

            fo.creation AS creation,
            foi.idx AS idx
        FROM `tabFactory OCR` fo
        INNER JOIN `tabFactory OCR Item` foi
            ON foi.parent = fo.name
            AND foi.parenttype = 'Factory OCR'
            AND foi.parentfield = 'table_ocn_details'
        WHERE fo.status = 'Approved'
          AND fo.docstatus < 2
        ORDER BY fo.creation DESC, fo.name DESC, foi.idx ASC
        """,
        as_dict=1
    ) or []

    data = []
    sl = 1
    for r in rows:
        order_qty = flt(r.get("order_quantity"))
        cut_qty = flt(r.get("cut_quantity"))
        ship_qty = flt(r.get("ship_quantity"))

        # Difference column
        # Prefer stored cut_to_ship_diff; fallback to (ship - cut)
        diff = r.get("cut_to_ship_diff")
        diff = flt(diff) if diff is not None else flt(ship_qty - cut_qty)

        # % columns (fallback compute if not stored)
        cut_to_ship = r.get("cut_to_ship")
        if cut_to_ship is None:
            cut_to_ship = (ship_qty / cut_qty * 100) if cut_qty else 0
        cut_to_ship = flt(cut_to_ship, 2)

        order_to_ship = r.get("order_to_ship")
        if order_to_ship is None:
            order_to_ship = (ship_qty / order_qty * 100) if order_qty else 0
        order_to_ship = flt(order_to_ship, 2)

        status_text = "Approved with Replenishment" if int(r.get("with_replenishment") or 0) == 1 else "Approved"

        data.append({
            "sl_no": sl,
            "ocn": r.get("ocn"),
            "style": r.get("style"),
            "colour": r.get("colour"),
            "order_quantity": flt(order_qty),
            "cut_quantity": flt(cut_qty),
            "scan_quantity": flt(r.get("scan_quantity")),
            "pack_quantity": flt(r.get("pack_quantity")),
            "ship_quantity": flt(ship_qty),
            "good_garments": flt(r.get("good_garments")),
            "rejected_garments": flt(r.get("rejected_garments")),
            "rejected_panels": flt(r.get("rejected_panels")),
            "difference": flt(diff),
            "cut_to_ship": cut_to_ship,
            "order_to_ship": order_to_ship,
            "status_text": status_text,
        })
        sl += 1

    return columns, data
