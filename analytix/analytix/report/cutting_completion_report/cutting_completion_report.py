# Copyright (c) 2025, Cognitonx Logic India Private limited and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("OCN"), "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": _("Style"), "fieldname": "style", "fieldtype": "Data", "width": 120},
        {"label": _("Colour"), "fieldname": "colour", "fieldtype": "Data", "width": 120},
        # {"label": _("Cut Docket"), "fieldname": "cut_docket", "fieldtype": "Link", "options": "Cut Docket", "width": 140},

        {"label": _("Order Qty"), "fieldname": "order_qty", "fieldtype": "Int", "width": 100},
        {"label": _("Fabric Ordered"), "fieldname": "fabric_ordered", "fieldtype": "Float", "width": 120},
        {"label": _("Fabric Issued"), "fieldname": "fabric_issued", "fieldtype": "Float", "width": 140},
        {"label": _("Folding"), "fieldname": "folding", "fieldtype": "Data", "width": 120},

        {"label": _("Calculated End Bit"), "fieldname": "calculated_end_bit", "fieldtype": "Float", "width": 120},
        {"label": _("Actual End Bit"), "fieldname": "actual_end_bit", "fieldtype": "Float", "width": 120},
        {"label": _("Chindi Weight"), "fieldname": "chindi_weight", "fieldtype": "Float", "width": 120},

        {"label": _("Balance as per Lay Record"), "fieldname": "balance_as_per_lay_record", "fieldtype": "Float", "width": 180},

        {"label": _("File Consumption"), "fieldname": "file_consumption", "fieldtype": "Float", "width": 140, "total": "avg"},
        {"label": _("Actual Consumption"), "fieldname": "actual_consumption", "fieldtype": "Float", "width": 160, "total": "avg"},
        {"label": _("Can Cut Qty"), "fieldname": "can_cut_qty", "fieldtype": "Int", "width": 100},

        {"label": _("Cut Qty Actual"), "fieldname": "cut_qty_actual", "fieldtype": "Int", "width": 120},
        {"label": _("Difference"), "fieldname": "difference", "fieldtype": "Int", "width": 100},
        {"label": _("Cut Completion %"), "fieldname": "cut_completion_pct", "fieldtype": "Percent", "width": 150},
        {"label": _("Last Cut Date"), "fieldname": "last_cut_date", "fieldtype": "Date", "width": 160},

        {"label": _("Profit loss Fabric"), "fieldname": "pl_fabric", "fieldtype": "Currency", "width": 150},
        {"label": _("Profit loss Merchant"), "fieldname": "pl_merchant", "fieldtype": "Currency", "width": 150},

        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": _("Approval"), "fieldname": "approval", "fieldtype": "Data", "width": 120},

        {"label": _("With Replenishment"), "fieldname": "with_replenishment", "fieldtype": "Check", "hidden": 1},

        {"label": _("Approved By"), "fieldname": "custom_approved_by", "fieldtype": "Link", "options": "User", "width": 140},
        {"label": _("Approved On"), "fieldname": "custom_approved_on", "fieldtype": "Datetime", "width": 160},

        # helper fields for your frontend grouping (optional)
        {"label": _("Row No"), "fieldname": "rn", "fieldtype": "Int", "width": 80, "hidden": 1},
        {"label": _("Is First Row"), "fieldname": "is_first_row", "fieldtype": "Check", "width": 100, "hidden": 1},

        # Size-wise balance JSON for hover popup
        {"label": _("Size Wise Balance"), "fieldname": "size_wise_balance", "fieldtype": "Data", "width": 0, "hidden": 1},
    ]


def get_data(filters):
    # -------------------------
    # Build conditions (reuse across queries)
    # -------------------------
    where_so = "so.docstatus = 1"
    params = {}

    if filters.get("from_date"):
        where_so += " AND so.delivery_date >= %(from_date)s"
        params["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        where_so += " AND so.delivery_date <= %(to_date)s"
        params["to_date"] = filters["to_date"]

    if filters.get("ocn"):
        where_so += " AND so.name = %(ocn)s"
        params["ocn"] = filters["ocn"]

    # -------------------------
    # 1) order_base: SO + style + colour summary
    # Pre-aggregate SO Items BEFORE any other joins to prevent row multiplication
    # -------------------------
    q_order_base = f"""
        SELECT
            so.name AS ocn,
            soi_agg.style,
            soi_agg.colour,
            soi_agg.order_qty,
            so.delivery_date,

            cc.fabric_ordered,
            cc.fabric_issued,
            cc.folding,

            clr.end_bit_quantity        AS calculated_end_bit,
            clr.actual_end_bit_quanity  AS actual_end_bit,
            clr.chindi_weight           AS chindi_weight,

            cc.file_consumption,
            cc.actual_consumption,
            cc.name AS can_cut_name,
            cc.with_replenishment,

            COALESCE(CASE WHEN cc.deviation_under = 'Fabric'   THEN cc.profit_loss_value END, 0) AS pl_fabric,
            COALESCE(CASE WHEN cc.deviation_under = 'Merchant' THEN cc.profit_loss_value END, 0) AS pl_merchant,

            so.custom_consumption_status AS consumption_status,
            so.custom_approval           AS approval,
            so.custom_approved_by,
            so.custom_approved_on

        FROM `tabSales Order` so

        INNER JOIN (
            SELECT
                sod.parent                  AS ocn,
                item.custom_style_master    AS style,
                sod.custom_color            AS colour,
                SUM(sod.qty)   AS order_qty
            FROM `tabSales Order Item` sod
            INNER JOIN `tabItem` item ON item.name = sod.item_code
            GROUP BY sod.parent, item.custom_style_master, sod.custom_color
        ) soi_agg ON soi_agg.ocn = so.name

        LEFT JOIN `tabCan Cut` cc
            ON cc.sales_order = so.name
            AND cc.colour = soi_agg.colour

        LEFT JOIN (
            SELECT
                ocn,
                colour,
                SUM(end_bit_quantity)       AS end_bit_quantity,
                SUM(actual_end_bit_quanity) AS actual_end_bit_quanity,
                SUM(chindi_weight)          AS chindi_weight
            FROM `tabCutting Lay Record`
            WHERE docstatus = 1
            GROUP BY ocn, colour
        ) clr ON clr.ocn = so.name AND clr.colour = soi_agg.colour

        WHERE {where_so}
    """
    order_rows = frappe.db.sql(q_order_base, params, as_dict=1)

    if not order_rows:
        return []

    # Build a fast lookup for base rows by (ocn, colour)
    base_by_key = {}
    ocn_set = set()

    for r in order_rows:
        ocn_set.add(r["ocn"])
        base_by_key[(r["ocn"], r["colour"])] = r

    # -------------------------
    # Prepare "IN" filters for the other queries
    # -------------------------
    ocn_list = sorted(list(ocn_set))
    if not ocn_list:
        return []

    params_in = dict(params)
    params_in["ocn_list"] = tuple(ocn_list)

    # -------------------------
    # 2) cut_by_docket: SO + colour + cut_docket
    # -------------------------
    q_cut_by_docket = """
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
          AND cci.sales_order IN %(ocn_list)s
        GROUP BY cci.sales_order, cd.color, cd.name
    """
    cut_rows = frappe.db.sql(q_cut_by_docket, params_in, as_dict=1)

    # -------------------------
    # 3) grn_by_colour: SO + colour
    # -------------------------
    q_grn_by_colour = """
        SELECT
            grn.ocn AS ocn,
            gri.color AS colour,
            SUM(gri.received_quantity) AS received_qty
        FROM `tabGoods Receipt Note` grn
        INNER JOIN `tabGoods Receipt Item` gri ON gri.parent = grn.name
        WHERE grn.docstatus = 1
          AND grn.ocn IN %(ocn_list)s
        GROUP BY grn.ocn, gri.color
    """
    grn_rows = frappe.db.sql(q_grn_by_colour, params_in, as_dict=1)
    grn_map = {(r["ocn"], r["colour"]): (r.get("received_qty") or 0) for r in grn_rows}

    # -------------------------
    # 4) lay_actual_by_colour: SO + colour
    # -------------------------
    q_lay_actual_by_colour = """
        SELECT
            clr2.ocn AS ocn,
            clr2.colour AS colour,
            SUM(lrd.actual_total) AS lay_actual_total
        FROM `tabCutting Lay Record` clr2
        INNER JOIN `tabLay Roll Details` lrd ON lrd.parent = clr2.name
        WHERE clr2.docstatus = 1
          AND clr2.ocn IN %(ocn_list)s
        GROUP BY clr2.ocn, clr2.colour
    """
    lay_rows = frappe.db.sql(q_lay_actual_by_colour, params_in, as_dict=1)
    lay_map = {(r["ocn"], r["colour"]): (r.get("lay_actual_total") or 0) for r in lay_rows}

    # -------------------------
    # 5) last_cut_date: SO + colour → max(cut confirmation creation)
    # -------------------------
    q_last_cut_date = """
        SELECT
            cci.sales_order AS ocn,
            cd.color AS colour,
            MAX(con.creation) AS last_cut_date
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` con ON con.name = cci.parent
        INNER JOIN `tabCut Docket` cd ON cd.name = con.cut_po_number
        WHERE cci.docstatus = 1
          AND con.docstatus = 1
          AND cci.sales_order IN %(ocn_list)s
        GROUP BY cci.sales_order, cd.color
    """
    last_cut_rows = frappe.db.sql(q_last_cut_date, params_in, as_dict=1)
    last_cut_map = {(r["ocn"], r["colour"]): r["last_cut_date"] for r in last_cut_rows}

    # -------------------------
    # 6) size_wise_order_qty: SO + colour + size from Sales Order Item
    # Use float to preserve decimals and match the totals calculation
    # -------------------------
    q_size_order_qty = """
        SELECT
            sod.parent              AS ocn,
            sod.custom_color        AS colour,
            sod.custom_size         AS size,
            SUM(sod.qty) AS order_qty
        FROM `tabSales Order Item` sod
        WHERE sod.parent IN %(ocn_list)s
        GROUP BY sod.parent, sod.custom_color, sod.custom_size
        ORDER BY sod.parent, sod.custom_color, sod.custom_size
    """
    size_order_rows = frappe.db.sql(q_size_order_qty, params_in, as_dict=1)

    # Build map: (ocn, colour) → { size: order_qty }  — keep as float
    size_order_map = {}
    for r in size_order_rows:
        key = (r["ocn"], r["colour"])
        size_order_map.setdefault(key, {})[r.get("size") or ""] = float(r.get("order_qty") or 0)

    # -------------------------
    # 7) size_wise_cut_qty: SO + colour + size from Cut Confirmation Item
    # Use float to preserve decimals and match the totals calculation
    # -------------------------
    q_size_cut_qty = """
        SELECT
            cci.sales_order         AS ocn,
            cd.color                AS colour,
            cci.size                AS size,
            SUM(cci.confirmed_quantity) AS cut_qty
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation` con ON con.name = cci.parent
        INNER JOIN `tabCut Docket`       cd  ON cd.name  = con.cut_po_number
        WHERE cci.docstatus = 1
          AND con.docstatus = 1
          AND cci.sales_order IN %(ocn_list)s
        GROUP BY cci.sales_order, cd.color, cci.size
        ORDER BY cci.sales_order, cd.color, cci.size
    """
    size_cut_rows = frappe.db.sql(q_size_cut_qty, params_in, as_dict=1)

    # Build map: (ocn, colour) → { size: cut_qty }  — keep as float
    size_cut_map = {}
    for r in size_cut_rows:
        key = (r["ocn"], r["colour"])
        size_cut_map.setdefault(key, {})[r.get("size") or ""] = float(r.get("cut_qty") or 0)

    # Combine into size_wise_balance_map: (ocn, colour) → [ {size, order_qty, cut_qty, balance} ]
    # Union of all sizes from both order and cut; balance = cut_qty - order_qty (same direction as Difference column)
    size_wise_balance_map = {}
    all_keys = set(size_order_map.keys()) | set(size_cut_map.keys())
    for key in all_keys:
        order_by_size = size_order_map.get(key, {})
        cut_by_size   = size_cut_map.get(key, {})
        all_sizes = sorted(set(list(order_by_size.keys()) + list(cut_by_size.keys())))
        rows = []
        for size in all_sizes:
            oq = order_by_size.get(size, 0.0)
            cq = cut_by_size.get(size, 0.0)
            rows.append({
                "size":      size,
                "order_qty": round(oq, 2),
                "cut_qty":   round(cq, 2),
                "balance":   round(cq - oq, 2),   # same direction as Difference column (cut - order)
            })
        size_wise_balance_map[key] = rows

    # -------------------------
    # Build final rows (one per docket)
    # -------------------------
    final = []

    if cut_rows:
        for c in cut_rows:
            key = (c["ocn"], c["colour"])
            base = base_by_key.get(key)
            if not base:
                continue
            row = dict(base)
            row["cut_docket"]     = c.get("cut_docket")
            row["cut_qty_actual"] = int(c.get("cut_qty_actual") or 0)
            row["last_cut_date"]  = last_cut_map.get(key)
            row = _apply_python_derivations(row, grn_map, lay_map, size_wise_balance_map)
            final.append(row)

    # Emit rows where there is no cut docket (LEFT JOIN behaviour)
    docket_keys = {(r["ocn"], r["colour"]) for r in cut_rows} if cut_rows else set()
    for (ocn, colour), base in base_by_key.items():
        if (ocn, colour) in docket_keys:
            continue
        row = dict(base)
        row["cut_docket"]     = None
        row["cut_qty_actual"] = 0
        row = _apply_python_derivations(row, grn_map, lay_map, size_wise_balance_map)
        final.append(row)

    # -------------------------
    # Filter out "Yet to Start" cases
    # -------------------------
    final = [row for row in final if row.get("status") != "Yet to Start"]

    # -------------------------
    # rn + is_first_row (partition by ocn)
    # -------------------------
    final.sort(key=lambda r: (
        r.get("delivery_date") or "",
        r.get("ocn") or "",
        r.get("colour") or "",
        r.get("cut_docket") or ""
    ))

    rn_counter = {}
    for r in final:
        ocn = r.get("ocn")
        rn_counter[ocn] = rn_counter.get(ocn, 0) + 1
        r["rn"] = rn_counter[ocn]
        r["is_first_row"] = 1 if r["rn"] == 1 else 0

    # Final sort
    final.sort(key=lambda r: (
        r.get("status") or "",
        r.get("delivery_date") or "",
        r.get("ocn") or "",
        r.get("rn") or 0
    ))

    return final


def _apply_python_derivations(row, grn_map, lay_map, size_wise_balance_map=None):
    """
    Fill derived fields:
    - can_cut_qty
    - difference
    - balance_as_per_lay_record
    - cut_completion_pct
    - status
    - size_wise_balance (JSON for hover popup)
    """
    order_qty      = float(row.get("order_qty") or 0)
    cut_qty_actual = float(row.get("cut_qty_actual") or 0)

    # can_cut_qty
    fabric_issued      = float(row.get("fabric_issued") or 0)
    actual_consumption = float(row.get("actual_consumption") or 0)
    if actual_consumption > 0:
        row["can_cut_qty"] = int(round(fabric_issued / actual_consumption))
    else:
        row["can_cut_qty"] = 0

    # difference (cut - order, same direction as size-wise balance)
    row["difference"] = int(round(cut_qty_actual - order_qty))

    # balance_as_per_lay_record
    ocn    = row.get("ocn")
    colour = row.get("colour")
    received_qty     = float(grn_map.get((ocn, colour), 0) or 0)
    lay_actual_total = float(lay_map.get((ocn, colour), 0) or 0)
    frappe.log(f"DEBUG - OCN: {ocn}, Colour: {colour}, Received Qty: {received_qty}, Lay Actual Total: {lay_actual_total}")
    row["balance_as_per_lay_record"] = received_qty - lay_actual_total

    # cut completion %
    if order_qty > 0:
        row["cut_completion_pct"] = (cut_qty_actual / order_qty) * 100.0
    else:
        row["cut_completion_pct"] = 0.0

    # status
    cs = row.get("consumption_status")
    if isinstance(cs, str) and cs.strip():
        row["status"] = cs
    elif cut_qty_actual == 0 or order_qty == 0:
        row["status"] = "Yet to Start"
    else:
        pct = (cut_qty_actual / order_qty) * 100.0
        row["status"] = "Inprogress" if pct < 98 else "Completed"

    # Ensure pl fields are always numeric
    row["pl_fabric"]   = float(row.get("pl_fabric") or 0)
    row["pl_merchant"] = float(row.get("pl_merchant") or 0)

    # Size-wise balance JSON for hover popup
    # balance = cut_qty - order_qty per size (same direction as the Difference column)
    key = (ocn, colour)
    row["size_wise_balance"] = json.dumps(
        (size_wise_balance_map or {}).get(key, [])
    )

    return row