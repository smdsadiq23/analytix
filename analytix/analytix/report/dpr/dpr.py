# Copyright (c) 2025, Cognitonx Logic India Private limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from collections import defaultdict


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("OCN"), "fieldname": "ocn", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": _("Style"), "fieldname": "style", "fieldtype": "Data", "width": 120},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Data", "width": 100},
        {"label": _("Colour"), "fieldname": "colour", "fieldtype": "Data", "width": 100},
        {"label": _("Ord Qty"), "fieldname": "order_qty", "fieldtype": "Int", "width": 80},
        {"label": _("Cut Qty"), "fieldname": "cut_quantity", "fieldtype": "Int", "width": 80},
        {"label": _("Cut %"), "fieldname": "cut_pct", "fieldtype": "Percent", "width": 100, "precision": 1},
        {"label": _("Cut Bal"), "fieldname": "cut_balance", "fieldtype": "Int", "width": 80},
        {"label": _("Last Cut Date"), "fieldname": "last_cut_date", "fieldtype": "Date", "width": 120},
        {"label": _("CCR Status"), "fieldname": "custom_consumption_status", "fieldtype": "Data", "width": 100},
        {"label": _("Sew Qty"), "fieldname": "sew_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Sew Bal"), "fieldname": "sew_balance", "fieldtype": "Int", "width": 80},
        {"label": _("Scan Qty"), "fieldname": "scan_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Pack Qty"), "fieldname": "pack_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Pack Bal"), "fieldname": "pack_balance", "fieldtype": "Int", "width": 90},
        {"label": _("Ship Qty"), "fieldname": "ship_quantity", "fieldtype": "Int", "width": 100},
        {"label": _("Cut to Pack %"), "fieldname": "cut_to_pack", "fieldtype": "Percent", "width": 120, "precision": 1},
        {"label": _("Order to Pack %"), "fieldname": "order_to_pack", "fieldtype": "Percent", "width": 120, "precision": 1},
        {"label": _("OCR Status"), "fieldname": "ocr_status", "fieldtype": "Data", "width": 120},
        {"label": _("Dispatch Qty"), "fieldname": "dispatch_quantity", "fieldtype": "Int", "width": 120},
        {"label": _("Bal to Dispatch"), "fieldname": "bal_to_dispatch", "fieldtype": "Int", "width": 120},
        {"label": _("Dead Stock"), "fieldname": "dead_stock", "fieldtype": "Int", "width": 100},
    ]


# ─── priority for sorting ────────────────────────────────────────────────────
_APPROVAL_PRIORITY = {
    "Inprogress": 0,
    "Yet to Confirm": 1,
    "Completed": 2,
    "Approved": 3,
    "App with Replenishment": 4,
}


def _pct(numerator, denominator):
    return (numerator / denominator * 100.0) if denominator else 0.0


def get_data(filters):
    # ── 1. Main query — Sales Orders + Can Cut merged in one hit ─────────────
    base_rows = frappe.db.sql("""
        SELECT
            so.name                         AS ocn,
            item.custom_style_master        AS style,
            sod.custom_color                AS colour,
            SUM(sod.custom_order_qty)       AS order_qty,
            so.custom_approval              AS custom_consumption_status,
            so.custom_consumption_status    AS status,
            so.delivery_date,
            MAX(cc.with_replenishment)      AS with_replenishment
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` sod ON sod.parent = so.name
        INNER JOIN `tabItem` item            ON item.name  = sod.item_code
        LEFT  JOIN `tabCan Cut` cc
               ON  cc.sales_order = so.name
               AND cc.colour      = sod.custom_color
        WHERE so.docstatus = 1
        GROUP BY so.name, item.custom_style_master, sod.custom_color
        ORDER BY so.delivery_date, so.name, sod.custom_color
    """, as_dict=1)

    if not base_rows:
        return []

    ocn_list = tuple({r["ocn"] for r in base_rows})

    # ── 2. Cut quantities ────────────────────────────────────────────────────
    cut_map = {}
    for c in frappe.db.sql("""
        SELECT
            cci.sales_order             AS ocn,
            cd.color                    AS colour,
            fbu.factory_name            AS unit,
            SUM(cci.confirmed_quantity) AS cut_quantity,
            MAX(con.creation)           AS last_cut_date
        FROM `tabCut Confirmation Item` cci
        INNER JOIN `tabCut Confirmation`      con ON con.name = cci.parent
        INNER JOIN `tabCut Docket`             cd ON cd.name  = con.cut_po_number
        LEFT  JOIN `tabFactory Business Unit` fbu ON fbu.name = cd.factory_business_unit
        WHERE cci.docstatus = 1
          AND con.docstatus = 1
          AND cci.sales_order IN %(ocn_list)s
        GROUP BY cci.sales_order, cd.color
    """, {"ocn_list": ocn_list}, as_dict=1):
        cut_map[(c["ocn"], c["colour"])] = {
            "cut_quantity": int(c.get("cut_quantity") or 0),
            "last_cut_date": c.get("last_cut_date"),
            "unit": c.get("unit") or "",
        }

    # ── 3. Factory OCR ───────────────────────────────────────────────────────
    factory_map = {}
    for f in frappe.db.sql("""
        SELECT
            fo.ocn                  AS ocn,
            foi.colour              AS colour,
            foi.scan_quantity,
            foi.pack_quantity,
            foi.ship_quantity,
            foi.cut_to_ship,
            foi.order_to_ship,
            fo.with_replenishment,
            fo.status               AS factory_status
        FROM `tabFactory OCR` fo
        INNER JOIN `tabFactory OCR Item` foi
               ON  foi.parent      = fo.name
               AND foi.parenttype  = 'Factory OCR'
               AND foi.parentfield = 'table_ocn_details'
        WHERE fo.status    = 'Approved'
          AND fo.docstatus < 2
          AND fo.ocn       IN %(ocn_list)s
    """, {"ocn_list": ocn_list}, as_dict=1):
        factory_map[(f["ocn"], f["colour"])] = {
            "scan_quantity":      float(f.get("scan_quantity") or 0),
            "pack_quantity":      float(f.get("pack_quantity") or 0),
            "ship_quantity":      float(f.get("ship_quantity") or 0),
            "cut_to_ship":        float(f.get("cut_to_ship") or 0),
            "order_to_ship":      float(f.get("order_to_ship") or 0),
            "with_replenishment": int(f.get("with_replenishment") or 0),
            "factory_status":     f.get("factory_status") or "",
        }

    # ── 4. Sew + Scan in ONE query via UNION ALL, aggregated in Python ────────
    #    Avoids two heavy identical-structure queries hitting the same tables.
    #    The 'qty_type' discriminator tells us which bucket each row belongs to.
    sew_map  = defaultdict(float)
    scan_map = defaultdict(float)

    for r in frappe.db.sql("""
        SELECT
            'sew'                    AS qty_type,
            itm.custom_colour_name   AS colour,
            tbc.sales_order          AS ocn,
            pi.quantity              AS qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order`  tor ON tor.name = tbc.parent AND tor.item IS NOT NULL
        INNER JOIN `tabItem`            itm ON itm.name = tor.item
        INNER JOIN `tabProduction Item` pi  ON pi.tracking_order      = tor.name
                                          AND pi.bundle_configuration  = tbc.name
        INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabItem Scan Log`   isl ON isl.production_item = pi.name
                                          AND isl.operation LIKE 'Sewing Incoming%%'
                                          AND isl.log_status = 'Completed'
                                          AND isl.status IN ('Counted', 'Activated', 'Pass')
        WHERE tbc.sales_order IN %(ocn_list)s

        UNION ALL

        SELECT
            'scan'                   AS qty_type,
            itm.custom_colour_name   AS colour,
            tbc.sales_order          AS ocn,
            pi.quantity              AS qty
        FROM `tabTracking Order Bundle Configuration` tbc
        INNER JOIN `tabTracking Order`  tor   ON tor.name = tbc.parent AND tor.item IS NOT NULL
        INNER JOIN `tabItem`            itm   ON itm.name = tor.item
        INNER JOIN `tabProduction Item` pi    ON pi.tracking_order      = tor.name
                                            AND pi.bundle_configuration  = tbc.name
        INNER JOIN `tabTracking Component`        tc    ON tc.name = pi.component AND tc.is_main = 1
        INNER JOIN `tabCut Kit Plan Bundle Details` ckpbd ON ckpbd.production_item_id = pi.name
        INNER JOIN `tabCut Kit Plan`               ckp   ON ckp.name = ckpbd.parent
        INNER JOIN `tabItem Scan Log`              isl   ON isl.production_item = pi.name
                                                        AND isl.operation       = ckp.last_operation
                                                        AND isl.log_status      = 'Completed'
                                                        AND isl.status IN ('Counted', 'Activated', 'Pass')
        WHERE tbc.sales_order IN %(ocn_list)s
    """, {"ocn_list": ocn_list}, as_dict=1):
        key = (r["ocn"], r["colour"])
        if r["qty_type"] == "sew":
            sew_map[key]  += float(r["qty"] or 0)
        else:
            scan_map[key] += float(r["qty"] or 0)

    # ── 5. Dead-stock — only for Verified OCNs; GRN + Lay in ONE UNION ALL ───
    #    Saves a DB round-trip by collapsing two queries into one,
    #    then splitting them in Python.
    verified_ocns = tuple({r["ocn"] for r in base_rows if (r.get("status") or "") == "Verified"})

    grn_map = defaultdict(float)
    lay_map = defaultdict(float)

    if verified_ocns:
        for r in frappe.db.sql("""
            SELECT 'grn' AS src, grn.ocn AS ocn, gri.color AS colour, gri.received_quantity AS qty
            FROM `tabGoods Receipt Note` grn
            INNER JOIN `tabGoods Receipt Item` gri ON gri.parent = grn.name
            INNER JOIN `tabSales Order`        so  ON so.name    = grn.ocn
            WHERE grn.docstatus = 1
              AND so.custom_consumption_status = 'Verified'
              AND grn.ocn IN %(verified_ocns)s

            UNION ALL

            SELECT 'lay' AS src, clr.ocn AS ocn, clr.colour AS colour, lrd.actual_total AS qty
            FROM `tabCutting Lay Record` clr
            INNER JOIN `tabLay Roll Details` lrd ON lrd.parent = clr.name
            INNER JOIN `tabSales Order`       so ON so.name    = clr.ocn
            WHERE clr.docstatus = 1
              AND so.custom_consumption_status = 'Verified'
              AND clr.ocn IN %(verified_ocns)s
        """, {"verified_ocns": verified_ocns}, as_dict=1):
            key = (r["ocn"], r["colour"])
            if r["src"] == "grn":
                grn_map[key] += float(r["qty"] or 0)
            else:
                lay_map[key] += float(r["qty"] or 0)

    # ── 6. Build final rows in pure Python ───────────────────────────────────
    _empty_factory = {
        "scan_quantity": 0.0, "pack_quantity": 0.0, "ship_quantity": 0.0,
        "cut_to_ship": 0.0,   "order_to_ship": 0.0,
        "with_replenishment": 0, "factory_status": "",
    }

    final_rows = []
    for row in base_rows:
        key      = (row["ocn"], row["colour"])
        cut_data = cut_map.get(key) or {"cut_quantity": 0, "last_cut_date": None, "unit": ""}
        fdata    = factory_map.get(key) or _empty_factory

        order_qty = float(row.get("order_qty") or 0)
        cut_qty   = float(cut_data["cut_quantity"])
        sew_qty   = sew_map[key]          # defaultdict → 0.0 if missing
        pack_qty  = float(fdata["pack_quantity"])
        ship_qty  = float(fdata["ship_quantity"])

        row["cut_quantity"]  = int(cut_qty)
        row["last_cut_date"] = cut_data["last_cut_date"]
        row["unit"]          = cut_data["unit"]
        row["sew_quantity"]  = sew_qty
        row["sew_balance"]   = int(order_qty - sew_qty)
        row["scan_quantity"] = scan_map[key]
        row["pack_quantity"] = pack_qty
        row["ship_quantity"] = ship_qty

        row["cut_pct"]       = _pct(cut_qty, order_qty)
        row["cut_balance"]   = int(order_qty - cut_qty)
        row["pack_balance"]  = int(order_qty - pack_qty)
        row["cut_to_pack"]   = _pct(pack_qty, cut_qty)
        row["order_to_pack"] = _pct(pack_qty, order_qty)

        row["cut_to_ship"]   = fdata["cut_to_ship"]   or _pct(ship_qty, cut_qty)
        row["order_to_ship"] = fdata["order_to_ship"] or _pct(ship_qty, order_qty)

        row["dispatch_quantity"] = ship_qty
        row["bal_to_dispatch"]   = int(order_qty - ship_qty)

        # CCR / approval display
        raw_status = row.get("status") or ""
        approval   = row.get("custom_consumption_status") or ""
        with_replen = int(row.get("with_replenishment") or 0)

        if raw_status == "Verified" and not approval:
            display_approval = "Yet to Confirm"
        elif approval == "Approved":
            display_approval = "App with Replenishment" if with_replen else "Approved"
        else:
            display_approval = approval
        row["custom_consumption_status"] = display_approval

        # OCR Status
        f_status   = fdata["factory_status"]
        ocr_replen = fdata["with_replenishment"]
        row["ocr_status"] = (
            ("Approved with Replenishment" if ocr_replen == 1 else "Approved")
            if f_status == "Approved" else f_status
        )

        # Dead stock — only for Verified rows (maps are empty otherwise)
        row["dead_stock"] = (grn_map[key] - lay_map[key]) if raw_status == "Verified" else None

        final_rows.append(row)

    # ── 7. Sort ──────────────────────────────────────────────────────────────
    final_rows.sort(key=lambda r: (
        _APPROVAL_PRIORITY.get(r.get("custom_consumption_status", ""), 3),
        r.get("delivery_date") or "",
        r["ocn"],
        r["colour"],
    ))

    return final_rows