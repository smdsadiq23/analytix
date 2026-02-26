# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "ISL Name",
            "fieldname": "isl_name",
            "fieldtype": "Data",
            "width": 0,
            "hidden": 1,       # hidden but available in row data for save calls
        },
        {
            "label": "Process Date",
            "fieldname": "process_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Process Time",
            "fieldname": "process_time",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": "RFID Tag",
            "fieldname": "rfid_tag",
            "fieldtype": "Data",
            "width": 250,
        },
        {
            "label": "Buyer",
            "fieldname": "buyer",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Style",
            "fieldname": "style",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": "Colour",
            "fieldname": "colour",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": "Size",
            "fieldname": "size",
            "fieldtype": "Data",
            "width": 60,
        },
        {
            "label": "RFID Qty",
            "fieldname": "rfid_qty",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": "Actual Qty",
            "fieldname": "custom_actual_quantity",
            "fieldtype": "Int",
            "width": 110,
        },
        {
            "label": "Operator",
            "fieldname": "custom_operator",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 160,
        },
        {
            "label": "Planned Weight",
            "fieldname": "plnd_weight",
            "fieldtype": "Float",
            "width": 140,
        },        
        {
            "label": "Actual Weight",
            "fieldname": "custom_actual_weight",
            "fieldtype": "Float",
            "width": 140,
        },
        {
            "label": "Variance",
            "fieldname": "variance",
            "fieldtype": "Float",
            "width": 130,
        }       
    ]


def get_data(filters=None):
    return frappe.db.sql(
        """
        SELECT
            isl.name                                        AS isl_name,
            DATE(isl.logged_time)                           AS process_date,
            TIME(isl.logged_time)                           AS process_time,
            tt.tag_number                                   AS rfid_tag,
            so.customer_name                                AS buyer,
            itm.custom_style_master                         AS style,
            itm.custom_colour_name                          AS colour,
            tbc.size                                        AS size,
            pi.quantity                                     AS rfid_qty,
            (pi.quantity * bom.custom_final_piece_weight)   AS plnd_weight,
            isl.custom_actual_quantity                      AS custom_actual_quantity,
            isl.custom_operator                             AS custom_operator,
            isl.custom_actual_weight                        AS custom_actual_weight,
            CASE
                WHEN isl.custom_actual_weight IS NOT NULL
                THEN isl.custom_actual_weight - (pi.quantity * bom.custom_final_piece_weight)
                ELSE NULL
            END                                             AS variance            
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi
            ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor
            ON tor.name = pi.tracking_order
        INNER JOIN `tabProduction Item Tag Map` pitm
            ON pitm.production_item = pi.name
        INNER JOIN `tabTracking Tag` tt
            ON tt.name = pitm.tracking_tag
        INNER JOIN `tabTracking Order Bundle Configuration` tbc
            ON tbc.parent = tor.name AND tbc.name = pi.bundle_configuration
        INNER JOIN `tabItem` itm
            ON itm.name = tor.item
        INNER JOIN `tabBOM` bom
            ON bom.item = itm.name AND bom.is_default = 1
        INNER JOIN `tabPhysical Cell` pc
            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc
            ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabSales Order` so
            ON so.name = tbc.sales_order
        WHERE pc.cell_name = 'KNITTING'
            AND isl.operation = 'KNITTING OUT'
            AND isl.log_status = 'Completed'
            AND isl.status IN ('Counted', 'Pass')
        ORDER BY process_date DESC
        """,
        as_dict=True,
    )


@frappe.whitelist()
def save_knitting_entry(isl_name, fieldname, value):
    """
    Whitelisted method called from the report JS to persist
    edits to the three custom fields on Item Scan Log.
    """
    allowed_fields = {
        "custom_actual_quantity",
        "custom_operator",
        "custom_actual_weight",
    }
    if fieldname not in allowed_fields:
        frappe.throw(frappe._("Field {0} is not editable via this report.").format(fieldname))

    frappe.db.set_value("Item Scan Log", isl_name, fieldname, value or None)
    frappe.db.commit()
    return {"status": "ok"}