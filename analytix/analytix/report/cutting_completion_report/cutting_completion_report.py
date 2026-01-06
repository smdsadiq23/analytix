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
            "fieldtype": "Currency",
            "width": 150
        },            
        {
            "label": _("Profit loss Merchant"),
            "fieldname": "pl_merchant",
            "fieldtype": "Currency",
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
        WITH
        order_base AS (
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
                COALESCE(CASE WHEN deviation_under = 'Fabric' THEN cc.profit_loss_value END, 0) AS pl_fabric,
                COALESCE(CASE WHEN deviation_under = 'Merchant' THEN cc.profit_loss_value END, 0) AS pl_merchant,

                ROUND(
                    CASE
                        WHEN cc.actual_consumption > 0 THEN (cc.fabric_issued / cc.actual_consumption)
                        ELSE 0
                    END
                ) AS can_cut_qty,

                so.custom_consumption_status AS consumption_status,
                so.custom_approval AS approval,
                so.custom_approved_by,
                so.custom_approved_on

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

            GROUP BY so.name, item.custom_style_master, sod.custom_color
        ),

        cut_by_docket AS (
            SELECT
                cci.sales_order AS ocn,
                cd.color AS colour,
                cd.name AS cut_docket,
                SUM(cci.confirmed_quantity) AS cut_qty_actual
            FROM `tabCut Confirmation Item` cci
            INNER JOIN `tabCut Confirmation` con ON con.name = cci.parent
            INNER JOIN `tabCut Docket` cd ON cd.name = con.cut_po_number
            WHERE cci.docstatus = 1
            AND con.docstatus = 1
            GROUP BY cci.sales_order, cd.color, cd.name
        ),

        grn_by_colour AS (
            SELECT
                grn.ocn AS ocn,
                gri.color AS colour,
                SUM(gri.received_quantity) AS received_qty
            FROM `tabGoods Receipt Note` grn
            INNER JOIN `tabGoods Receipt Item` gri ON gri.parent = grn.name
            WHERE grn.docstatus = 1
            GROUP BY grn.ocn, gri.color
        ),

        lay_actual_by_colour AS (
            SELECT
                clr2.ocn AS ocn,
                clr2.colour AS colour,
                SUM(lrd.actual_total) AS lay_actual_total
            FROM `tabCutting Lay Record` clr2
            INNER JOIN `tabLay Roll Details` lrd ON lrd.parent = clr2.name
            WHERE clr2.docstatus = 1
            GROUP BY clr2.ocn, clr2.colour
        )

        SELECT
            final_q.*,
            CASE
                WHEN final_q.consumption_status IS NOT NULL AND final_q.consumption_status != ''
                    THEN final_q.consumption_status
                WHEN final_q.cut_qty_actual = 0 OR final_q.order_qty = 0
                    THEN 'Yet to Start'
                WHEN (final_q.cut_qty_actual / final_q.order_qty) * 100 < 98
                    THEN 'Inprogress'
                ELSE 'Completed'
            END AS status,
            CASE WHEN final_q.rn = 1 THEN 1 ELSE 0 END AS is_first_row
        FROM (
            SELECT
                ob.*,

                cbd.cut_docket,
                COALESCE(cbd.cut_qty_actual, 0) AS cut_qty_actual,
                ROUND(COALESCE(cbd.cut_qty_actual, 0) - ob.order_qty) AS difference,

                (COALESCE(grn.received_qty, 0) - COALESCE(lay.lay_actual_total, 0)) AS balance_as_per_lay_record,

                ROW_NUMBER() OVER (
                    PARTITION BY ob.ocn
                    ORDER BY ob.colour, cbd.cut_docket
                ) AS rn

            FROM order_base ob

            -- ✅ This is the key join that creates one row per Cut Docket
            LEFT JOIN cut_by_docket cbd
                ON cbd.ocn = ob.ocn
                AND cbd.colour = ob.colour

            LEFT JOIN grn_by_colour grn
                ON grn.ocn = ob.ocn
                AND grn.colour = ob.colour

            LEFT JOIN lay_actual_by_colour lay
                ON lay.ocn = ob.ocn
                AND lay.colour = ob.colour

        ) final_q
        ORDER BY status, delivery_date, ocn, rn
    """.format(conditions=conditions)


    data = frappe.db.sql(query, filters, as_dict=1)
    return data
