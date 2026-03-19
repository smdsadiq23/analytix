# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict
from frappe.utils import formatdate

# Only the LINKING cell is tracked in this dashboard
LINK_CELL = "LINKING"

# Standard garment size order (uppercase match)
_SIZE_ORDER = ["2XS", "XS", "S", "M", "L", "XL", "2XL", "XXL", "3XL", "XXXL", "4XL", "XXXXL"]


def _size_sort_key(size):
    """
    Smart sort key that handles both letter sizes (S/M/L/XL …)
    and numeric / age sizes (2YRS, 5YRS, 6, 8, 10 …).
    """
    upper = (size or "").upper().strip()

    # Standard garment sizes get a fixed rank (0‥N)
    if upper in _SIZE_ORDER:
        return (0, _SIZE_ORDER.index(upper), "")

    # Age / numeric prefix  e.g. "3YRS", "5YRS", "10", "12"
    import re
    m = re.match(r"^(\d+)", upper)
    if m:
        return (1, int(m.group(1)), upper)

    # Fallback – alphabetical
    return (2, 0, upper)


@frappe.whitelist()
def get_dashboard_data():
    order_map = _get_order_map()
    if not order_map:
        return []

    # LINKING cell IN (first operation) and OUT (last operation)
    cell_in_map  = _get_linking_op_map(op_type="first")
    cell_out_map = _get_linking_op_map(op_type="last")

    # Earliest scan_time per (style, colour, size) — for sort order
    scan_time_map = _get_min_scan_time_map()

    # ── Aggregate at (buyer, season, style, colour); keep per-size detail ────
    agg = defaultdict(lambda: {
        "order_qty":    0,
        "planned_qty":  0,
        "delivery_date": None,
        "min_scan_time": None,
        "sizes": {},              # size → {order_qty, planned_qty, in, out}
    })

    for (style, colour, size), info in order_map.items():
        key = (info.buyer or "", info.season or "", style, colour)

        row_order_qty   = int(info.order_qty   or 0)
        row_planned_qty = int(info.planned_qty or 0)

        agg[key]["order_qty"]   += row_order_qty
        agg[key]["planned_qty"] += row_planned_qty

        d = info.delivery_date
        if d and (agg[key]["delivery_date"] is None or d > agg[key]["delivery_date"]):
            agg[key]["delivery_date"] = d

        st = scan_time_map.get((style, colour, size))
        if st and (agg[key]["min_scan_time"] is None or st < agg[key]["min_scan_time"]):
            agg[key]["min_scan_time"] = st

        linking_in  = cell_in_map.get((style, colour, size, LINK_CELL), 0)
        linking_out = cell_out_map.get((style, colour, size, LINK_CELL), 0)

        agg[key]["sizes"][size] = {
            "order_qty":   row_order_qty,
            "planned_qty": row_planned_qty,
            "in":          linking_in,
            "out":         linking_out,
        }

    # ── Build result rows ─────────────────────────────────────────────────────
    sorted_keys = sorted(
        agg.keys(),
        key=lambda k: (
            agg[k]["min_scan_time"] is None,
            agg[k]["min_scan_time"] or "0000-00-00 00:00:00",
        )
    )

    result = []
    for buyer, season, style, colour in sorted_keys:
        b = agg[(buyer, season, style, colour)]

        order_qty   = b["order_qty"]
        planned_qty = b["planned_qty"]

        # Total LINKING output across all sizes
        total_linking_out = sum(s["out"] for s in b["sizes"].values())
        completion_pct    = round((total_linking_out / order_qty) * 100, 1) if order_qty else 0.0

        # Skip orders that are over-completed
        if completion_pct >= 105:
            continue

        delivery_date = ""
        if b["delivery_date"]:
            delivery_date = formatdate(b["delivery_date"], "dd-mm-yyyy")

        # Sort sizes with smart key so they render in logical order
        sorted_sizes = sorted(b["sizes"].items(), key=lambda kv: _size_sort_key(kv[0]))

        result.append({
            "style":              style,
            "buyer":              buyer,
            "colour":             colour,
            "season":             season,
            "delivery_date":      delivery_date,
            "order_qty":          order_qty,
            "planned_qty":        planned_qty,
            "sizes":              [
                {"size": sz, **data}
                for sz, data in sorted_sizes
            ],
            "total_linking_out":  total_linking_out,
            "completion_pct":     completion_pct,
        })

    return result


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_order_map():
    rows = frappe.db.sql("""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            so.custom_brand                             AS buyer,
            so.delivery_date                            AS delivery_date,
            stm.custom_season                           AS season,
            COALESCE(SUM(soi.custom_order_qty), 0)      AS order_qty,
            COALESCE(SUM(soi.qty), 0)                   AS planned_qty
        FROM (
            SELECT DISTINCT sales_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
        INNER JOIN `tabSales Order` so          ON so.name = tbc.sales_order
        INNER JOIN `tabSales Order Item` soi    ON soi.parent = so.name AND soi.custom_size = tbc.size
        INNER JOIN `tabItem` itm                ON itm.name = soi.item_code
        INNER JOIN `tabStyle Master` stm        ON stm.name = itm.custom_style_master
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size,
                 so.custom_brand, so.delivery_date, stm.custom_season
    """, as_dict=True)
    return {(r.style, r.colour, r.size): r for r in rows}


def _get_min_scan_time_map():
    """Earliest isl.scan_time per (style, colour, size) — used for row sorting."""
    rows = frappe.db.sql("""
        SELECT
            itm.custom_style_master  AS style,
            itm.custom_colour_name   AS colour,
            tbc.size                 AS size,
            MIN(isl.scan_time)       AS min_scan_time
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi      ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor      ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc                                   ON tbc.parent = tor.name
                                               AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                ON itm.name = tor.item
        WHERE isl.log_status = 'Completed'
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size
    """, as_dict=True)
    return {(r.style, r.colour, r.size): r.min_scan_time for r in rows}


def _get_linking_op_map(op_type="last"):
    """
    Returns LINKING qty per (style, colour, size) for either the
    first operation (cell IN) or the last operation (cell OUT).

    op_type = "first"  →  isl.operation = pcflo.first_operation  →  IN
    op_type = "last"   →  isl.operation = pcflo.last_operation   →  OUT
    """
    op_field = "first_operation" if op_type == "first" else "last_operation"

    rows = frappe.db.sql(f"""
        SELECT
            itm.custom_style_master                     AS style,
            itm.custom_colour_name                      AS colour,
            tbc.size                                    AS size,
            pc.cell_name                                AS cell_name,
            COALESCE(SUM(pi.quantity), 0)               AS qty
        FROM `tabItem Scan Log` isl
        INNER JOIN `tabProduction Item` pi          ON pi.name = isl.production_item
        INNER JOIN `tabTracking Order` tor          ON tor.name = pi.tracking_order
        INNER JOIN (
            SELECT DISTINCT parent, sales_order, work_order, size
            FROM `tabTracking Order Bundle Configuration`
            WHERE parentfield = 'bundle_configurations'
        ) tbc
            ON tbc.parent = tor.name AND tbc.size = pi.size
        INNER JOIN `tabItem` itm                    ON itm.name = tor.item
        INNER JOIN `tabPhysical Cell` pc            ON pc.name = isl.physical_cell
        INNER JOIN `tabTracking Component` tc       ON tc.name = pi.component
                                                   AND tc.is_main = 1
        INNER JOIN `tabPhysical Cell First and Last Operation` pcflo
                                                   ON pcflo.parent = tbc.work_order
                                                   AND pcflo.physical_cell = pc.name
        INNER JOIN `tabSales Order` so              ON so.name = tbc.sales_order
        WHERE isl.operation = pcflo.{op_field}
          AND isl.log_status = 'Completed'
          AND pc.cell_name = 'LINKING'
          AND (
              isl.status IN ('Counted', 'Activated', 'Pass')
              OR (isl.status = 'Unlink Link' AND pi.status = 'Unlink Link Scrap')
          )
        GROUP BY itm.custom_style_master, itm.custom_colour_name, tbc.size, pc.cell_name
    """, as_dict=True)

    return {(r.style, r.colour, r.size, r.cell_name): int(r.qty) for r in rows}
