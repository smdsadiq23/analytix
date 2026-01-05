# Copyright (c) 2025, Cognitonx Logic India Private limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": _("OCN"),
            "fieldname": "ocn",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 120
        },
        {
            "label": _("Style"),
            "fieldname": "style",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Colour"),
            "fieldname": "colour",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Order Qty"),
            "fieldname": "order_qty",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Fabric Ordered"),
            "fieldname": "fabric_ordered",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": _("Fabric Issued"),
            "fieldname": "fabric_issued",
            "fieldtype": "Float",
            "width": 140
        },
        {
            "label": _("Folding"),
            "fieldname": "folding",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Calculated End Bit"),
            "fieldname": "calculated_end_bit",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": _("Actual End Bit"),
            "fieldname": "actual_end_bit",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": _("Chindi Weight"),
            "fieldname": "chindi_weight",
            "fieldtype": "Float",
            "width": 120
        },        
        {
            "label": _("Balance as per Lay Record"),
            "fieldname": "balance_as_per_lay_record",
            "fieldtype": "Float",
            "width": 180
        },        
        {
            "label": _("File Consumption"),
            "fieldname": "file_consumption",
            "fieldtype": "Float",
            "width": 140,
            "total": "avg"
        },
        {
            "label": _("Actual Consumption"),
            "fieldname": "actual_consumption",
            "fieldtype": "Float",
            "width": 160,
            "total": "avg"
        },
        {
            "label": _("Can Cut Qty"),
            "fieldname": "can_cut_qty",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Cut Qty Actual"),
            "fieldname": "cut_qty_actual",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Difference"),
            "fieldname": "difference",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Cut Completion %"),
            "fieldname": "cut_completion_pct",
            "fieldtype": "Percent",
            "width": 150
        },
        {
            "label": _("Profit loss Fabric"),
            "fieldname": "pl_fabric",
            "fieldtype": "Percent",
            "width": 150
        },            
        {
            "label": _("Profit loss Merchant"),
            "fieldname": "pl_merchant",
            "fieldtype": "Percent",
            "width": 150
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Approval"),
            "fieldname": "approval",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("With Replenishment"),
            "fieldname": "with_replenishment",
            "fieldtype": "Check",
            "hidden": 1  # Hide from report
        },        
        {
            "label": _("Approved By"),
            "fieldname": "custom_approved_by",
            "fieldtype": "Link",
            "options": "User",
            "width": 140
        },
        {
            "label": _("Approved On"),
            "fieldname": "custom_approved_on",
            "fieldtype": "Datetime",
            "width": 160
        }
    ]


def get_data(filters):
    conditions = ""
    if filters.get("from_date"):
        conditions += " AND so.delivery_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND so.delivery_date <= %(to_date)s"

    query = """
        SELECT
            sub_query.*,
            CASE
                WHEN sub_query.consumption_status IS NOT NULL AND sub_query.consumption_status != ''
                    THEN sub_query.consumption_status
                WHEN sub_query.cut_qty_actual = 0 OR sub_query.order_qty = 0
                    THEN 'Yet to Start'
                WHEN (sub_query.cut_qty_actual / sub_query.order_qty) * 100 < 98
                    THEN 'Inprogress'
                ELSE
                    'Completed'
            END AS status,
            CASE WHEN rn = 1 THEN 1 ELSE 0 END AS is_first_row
        FROM (
            SELECT
                so.name AS ocn,
                item.custom_style_master AS style,
                sod.custom_color AS colour,
                SUM(sod.custom_order_qty) AS order_qty,
                so.delivery_date,

                cc.fabric_ordered,
                cc.fabric_issued,
                cc.folding,
                clr.end_bit_quantity AS calculated_end_bit,
                clr.actual_end_bit_quanity AS actual_end_bit,
                cc.file_consumption,
                cc.actual_consumption,
                cc.name AS can_cut_name,
                cc.with_replenishment,
                CASE WHEN deviation_under = 'Fabric' THEN cc.profit_loss_value END AS pl_fabric,
                CASE WHEN deviation_under = 'Merchant' THEN cc.profit_loss_value END AS pl_merchant,

                ROUND(
                    CASE 
                        WHEN cc.actual_consumption > 0 THEN (cc.fabric_issued / cc.actual_consumption)
                        ELSE 0
                    END
                ) AS can_cut_qty,

                COALESCE((
                    SELECT SUM(cci.confirmed_quantity)
                    FROM `tabCut Confirmation Item` cci
                    INNER JOIN `tabCut Confirmation` con ON con.name = cci.parent
                    INNER JOIN `tabCut Docket` cd ON cd.name = con.cut_po_number
                    WHERE cci.sales_order = so.name
                    AND cd.color = sod.custom_color
                    AND cci.docstatus = 1
                ), 0) AS cut_qty_actual,

                ROUND(
                    COALESCE((
                        SELECT SUM(cci.confirmed_quantity)
                        FROM `tabCut Confirmation Item` cci
                        INNER JOIN `tabCut Confirmation` con ON con.name = cci.parent
                        INNER JOIN `tabCut Docket` cd ON cd.name = con.cut_po_number
                        WHERE cci.sales_order = so.name
                        AND cd.color = sod.custom_color
                        AND cci.docstatus = 1
                    ), 0) - SUM(sod.custom_order_qty)
                ) AS difference,

                so.custom_consumption_status AS consumption_status,
                so.custom_approval AS approval,
                so.custom_approved_by,
                so.custom_approved_on,

                COALESCE((
                    SELECT SUM(gr_item.received_quantity)
                    FROM `tabGoods Receipt Note` grn
                    INNER JOIN `tabGoods Receipt Item` gr_item ON gr_item.parent = grn.name
                    WHERE grn.docstatus = 1
                    AND grn.ocn = so.name                -- ✅ ocn in Goods Receipt = Sales Order
                    AND gr_item.color = sod.custom_color
                ), 0)
                -
                -- ✅ Sum actual_total from Lay Roll Details
                COALESCE((
                    SELECT SUM(lrd.actual_total)
                    FROM `tabCutting Lay Record` clr2
                    INNER JOIN `tabLay Roll Details` lrd ON lrd.parent = clr2.name
                    WHERE clr2.ocn = so.name
                    AND clr2.colour = sod.custom_color
                    AND clr2.docstatus = 1
                ), 0)
                AS balance_as_per_lay_record,

                ROW_NUMBER() OVER (PARTITION BY so.name ORDER BY sod.custom_color) AS rn

            FROM `tabSales Order` so
            INNER JOIN `tabSales Order Item` sod ON sod.parent = so.name
            INNER JOIN `tabItem` item ON item.name = sod.item_code
            LEFT JOIN `tabCan Cut` cc 
                ON cc.sales_order = so.name 
                AND cc.colour = sod.custom_color

            LEFT JOIN (
                SELECT 
                    ocn, 
                    colour, 
                    SUM(end_bit_quantity) AS end_bit_quantity, 
                    SUM(actual_end_bit_quanity) AS actual_end_bit_quanity,
                    SUM(chindi_weight) AS chindi_weight
                FROM `tabCutting Lay Record` 
                WHERE docstatus = 1 
                GROUP BY ocn, colour
            ) clr ON clr.ocn = so.name AND clr.colour = sod.custom_color

            WHERE so.docstatus = 1
            {conditions}

            GROUP BY so.name, sod.custom_color, item.custom_style_master, cc.name
            ORDER BY so.delivery_date, so.name, sod.custom_color
        ) sub_query
        ORDER BY status, delivery_date, ocn, rn
    """.format(conditions=conditions)

    data = frappe.db.sql(query, filters, as_dict=1)
    return data
