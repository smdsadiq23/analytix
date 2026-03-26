# Copyright (c) 2026

import frappe
from collections import defaultdict
from datetime import date as _date
from frappe.utils import formatdate

CELL_ORDER = [
    "KNITTING","MENDING","WASHING","CUTTING","LINKING",
    "SEWING","EMBROIDERY","PRODUCTION","PRESSING",
    "FINAL CHECK","PACKING",
]


@frappe.whitelist()
def get_dashboard_data():
    order_map = _get_order_map()
    if not order_map:
        return []

    scan_rows = _get_all_scan_data(order_map)

    cell_in_map = {}
    cell_out_map = {}
    cell_in_date_map = {}
    cell_out_date_map = {}
    cell_completion_date_map = {}
    logged_time_map = {}
    knitting_logged_time_map = {}

    for r in scan_rows:
        k4 = (r.style, r.colour, r.size, r.cell_name)
        k3 = (r.style, r.colour, r.size)

        cell_in_map[k4] = int(r.cell_in_qty or 0)
        cell_out_map[k4] = int(r.cell_out_qty or 0)

        if r.cell_in_first_log:
            cell_in_date_map[k4] = r.cell_in_first_log
        if r.cell_out_first_log:
            cell_out_date_map[k4] = r.cell_out_first_log
        if r.completion_date:
            cell_completion_date_map[k4] = r.completion_date

        if r.min_logged_time:
            ex = logged_time_map.get(k3)
            if ex is None or r.min_logged_time < ex:
                logged_time_map[k3] = r.min_logged_time

        if r.cell_name == "KNITTING" and r.knitting_logged_time:
            ex = knitting_logged_time_map.get(k3)
            if ex is None or r.knitting_logged_time < ex:
                knitting_logged_time_map[k3] = r.knitting_logged_time

    agg = defaultdict(lambda: {
        "order_qty": 0,
        "planned_qty": 0,
        "delivery_date": None,
        "min_logged_time": None,
        "cell_in": defaultdict(int),
        "cell_out": defaultdict(int),
        "cell_in_date": {},
        "cell_out_date": {},
        "cell_completion_date": {},
        "knitting_first_logged": None,
    })

    for (style, colour, size), info in order_map.items():
        key = (info.buyer or "", info.season or "", style, colour)

        agg[key]["order_qty"] += int(info.order_qty or 0)
        agg[key]["planned_qty"] += int(info.planned_qty or 0)

        d = info.delivery_date
        if d and (agg[key]["delivery_date"] is None or d > agg[key]["delivery_date"]):
            agg[key]["delivery_date"] = d

        lt = logged_time_map.get((style, colour, size))
        if lt and (agg[key]["min_logged_time"] is None or lt < agg[key]["min_logged_time"]):
            agg[key]["min_logged_time"] = lt

        klt = knitting_logged_time_map.get((style, colour, size))
        if klt and (agg[key]["knitting_first_logged"] is None or klt < agg[key]["knitting_first_logged"]):
            agg[key]["knitting_first_logged"] = klt

        for cell in CELL_ORDER:
            agg[key]["cell_in"][cell] += cell_in_map.get((style, colour, size, cell), 0)
            agg[key]["cell_out"][cell] += cell_out_map.get((style, colour, size, cell), 0)

            in_d = cell_in_date_map.get((style, colour, size, cell))
            if in_d:
                ex = agg[key]["cell_in_date"].get(cell)
                if ex is None or in_d < ex:
                    agg[key]["cell_in_date"][cell] = in_d

            out_d = cell_out_date_map.get((style, colour, size, cell))
            if out_d:
                ex = agg[key]["cell_out_date"].get(cell)
                if ex is None or out_d < ex:
                    agg[key]["cell_out_date"][cell] = out_d

            comp_d = cell_completion_date_map.get((style, colour, size, cell))
            if comp_d:
                ex = agg[key]["cell_completion_date"].get(cell)
                if ex is None or comp_d > ex:
                    agg[key]["cell_completion_date"][cell] = comp_d

    result = []

    sorted_keys = sorted(
        agg.keys(),
        key=lambda k: (
            agg[k]["min_logged_time"] is None,
            agg[k]["min_logged_time"] or "0000-00-00 00:00:00",
        )
    )

    today = _date.today()

    def _to_date(dt):
        if dt is None:
            return None
        if hasattr(dt, "date"):
            return dt.date()
        if isinstance(dt, _date):
            return dt
        try:
            return _date.fromisoformat(str(dt)[:10])
        except Exception:
            return None

    NO_IN_CELLS = {"KNITTING", "FINAL CHECK"}

    for buyer, season, style, colour in sorted_keys:
        b = agg[(buyer, season, style, colour)]

        order_qty = b["order_qty"]
        planned_qty = b["planned_qty"]

        cells = {}
        for cell in CELL_ORDER:
            cell_in = b["cell_in"].get(cell, 0)
            cell_out = b["cell_out"].get(cell, 0)
            pct = round((cell_out / order_qty) * 100) if order_qty else 0

            ref_date = _to_date(
                b["cell_out_date"].get(cell) if cell in NO_IN_CELLS
                else b["cell_in_date"].get(cell)
            )

            if cell_out >= planned_qty and planned_qty > 0:
                end_date = _to_date(b["cell_completion_date"].get(cell)) or today
            else:
                end_date = today

            days = (end_date - ref_date).days if ref_date else None

            cells[cell] = {"in": cell_in, "out": cell_out, "pct": pct, "days": days}

        knitting_logged_ref = _to_date(b["knitting_first_logged"])
        lead_days = (today - knitting_logged_ref).days if knitting_logged_ref else None

        packing_out = cells["PACKING"]["out"]
        completion_pct = round((packing_out / order_qty) * 100, 1) if order_qty else 0.0

        delivery_date = ""
        if b["delivery_date"]:
            delivery_date = formatdate(b["delivery_date"], "dd-mm-yyyy")

        if completion_pct >= 105:
            continue
        if cells["KNITTING"]["in"] == 0:
            continue

        result.append({
            "style": style,
            "buyer": buyer,
            "colour": colour,
            "season": season,
            "delivery_date": delivery_date,
            "order_qty": order_qty,
            "planned_qty": planned_qty,
            "cells": cells,
            "completion_pct": completion_pct,
            "lead_days": lead_days,
        })

    return result


def _get_order_map():
    rows = frappe.db.sql("""
        SELECT
            itm.custom_style_master AS style,
            itm.custom_colour_name AS colour,
            tbc.size AS size,
            so.custom_brand AS buyer,
            so.delivery_date AS delivery_date,
            stm.custom_season AS season,
            COALESCE(SUM(soi.custom_order_qty), 0) AS order_qty,
            COALESCE(SUM(soi.qty), 0) AS planned_qty
        FROM (
            SELECT DISTINCT sales_order, size
            FROM `tabTracking Order Bundle Configuration`
        ) tbc
        INNER JOIN `tabSales Order` so ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name AND soi.custom_size = tbc.size
        INNER JOIN `tabItem` itm ON itm.name = soi.item_code
        INNER JOIN `tabStyle Master` stm ON stm.name = itm.custom_style_master
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size,
                 so.custom_brand, so.delivery_date, stm.custom_season
    """, as_dict=True)
    return {(r.style, r.colour, r.size): r for r in rows}


def _get_all_scan_data(order_map):
    cell_list = ", ".join([f"'{c}'" for c in CELL_ORDER])

    planned_rows = [
        f"SELECT {frappe.db.escape(style)} AS style, "
        f"{frappe.db.escape(colour)} AS colour, "
        f"{frappe.db.escape(size)} AS size, "
        f"{int(info.planned_qty or 0)} AS planned_qty"
        for (style, colour, size), info in order_map.items()
    ]

    planned_subquery = " UNION ALL ".join(planned_rows)

    rows = frappe.db.sql(f"""
        WITH base AS (
            SELECT
                itm.custom_style_master AS style,
                itm.custom_colour_name AS colour,
                tbc.size AS size,
                pc.cell_name AS cell_name,
                isl.logged_time AS log_time,
                pi.quantity AS quantity,

                CASE
                    WHEN pc.cell_name = 'MENDING' AND isl.operation = 'MENDING IN' THEN 1
                    WHEN pc.cell_name != 'MENDING' AND isl.operation = pcflo.first_operation THEN 1
                    ELSE 0
                END AS is_first_op,

                CASE
                    WHEN pc.cell_name = 'MENDING' AND isl.operation = 'MENDING OUT' THEN 1
                    WHEN pc.cell_name != 'MENDING' AND isl.operation = pcflo.last_operation THEN 1
                    ELSE 0
                END AS is_last_op,

                CASE WHEN pc.cell_name = 'KNITTING' THEN 1 ELSE 0 END AS is_knitting

            FROM `tabItem Scan Log` isl
            INNER JOIN `tabProduction Item` pi ON pi.name = isl.production_item
            INNER JOIN `tabTracking Order` tor ON tor.name = pi.tracking_order
            INNER JOIN (
                SELECT DISTINCT parent, sales_order, work_order, size
                FROM `tabTracking Order Bundle Configuration`
            ) tbc ON tbc.parent = tor.name AND tbc.size = pi.size
            INNER JOIN `tabItem` itm ON itm.name = tor.item
            INNER JOIN `tabPhysical Cell` pc ON pc.name = isl.physical_cell
            INNER JOIN `tabTracking Component` tc ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                ON pcflo.parent = tbc.work_order AND pcflo.physical_cell = pc.name

            WHERE isl.log_status = 'Completed'
              AND isl.logged_time IS NOT NULL
              AND pc.cell_name IN ({cell_list})
        ),

        agg AS (
            SELECT
                style, colour, size, cell_name,
                SUM(CASE WHEN is_first_op = 1 THEN quantity ELSE 0 END) AS cell_in_qty,
                MIN(CASE WHEN is_first_op = 1 THEN log_time END) AS cell_in_first_log,
                SUM(CASE WHEN is_last_op = 1 THEN quantity ELSE 0 END) AS cell_out_qty,
                MIN(CASE WHEN is_last_op = 1 THEN log_time END) AS cell_out_first_log,
                MIN(log_time) AS min_logged_time,
                MIN(CASE WHEN is_knitting = 1 THEN log_time END) AS knitting_logged_time
            FROM base
            GROUP BY style, colour, size, cell_name
        ),

        running AS (
            SELECT
                b.style, b.colour, b.size, b.cell_name, b.log_time,
                SUM(b.quantity) OVER (
                    PARTITION BY b.style, b.colour, b.size, b.cell_name
                    ORDER BY b.log_time
                ) AS running_out_qty,
                pq.planned_qty
            FROM base b
            INNER JOIN ({planned_subquery}) pq
                ON pq.style = b.style
                AND pq.colour = b.colour
                AND pq.size = b.size
            WHERE b.is_last_op = 1
        )

        SELECT
            agg.*,
            comp.completion_date
        FROM agg
        LEFT JOIN (
            SELECT style, colour, size, cell_name,
                   MIN(log_time) AS completion_date
            FROM running
            WHERE running_out_qty >= planned_qty
            GROUP BY style, colour, size, cell_name
        ) comp
        ON comp.style = agg.style
        AND comp.colour = agg.colour
        AND comp.size = agg.size
        AND comp.cell_name = agg.cell_name
    """, as_dict=True)

    return rows