# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    filters = filters or {}
    summary_so = get_summary_so(filters)
    summary_wo = get_summary_wo(filters)
    detail_so = get_detail_so(filters.get("sales_order"))
    detail_wo = get_detail_wo(filters.get("work_order"))

    return [], [], None, None, [
        {"name": "summary_so", "data": summary_so or []},
        {"name": "summary_wo", "data": summary_wo or []},
        {"name": "detail_so", "data": detail_so or {}},
        {"name": "detail_wo", "data": detail_wo or {}}
    ]


def get_summary_so(filters):
    """Per-Sales Order summary for a selected operation (dup-safe)."""
    if not filters.get("operation"):
        return []

    params = {"op": filters["operation"]}
    # Build SOI date filter once
    if filters.get("date_range"):
        start, end = filters["date_range"]
        params.update({"start": start, "end": end})
        date_pred = "DATE(soi.custom_ex_fty_date) BETWEEN %(start)s AND %(end)s"
    else:
        from frappe.utils import now_datetime
        params["year"] = now_datetime().year
        date_pred = "YEAR(soi.custom_ex_fty_date) = %(year)s"

    # DISTINCT SO list that passes FG + date
    return frappe.db.sql(
        f"""
        SELECT
            so.name AS so_number,
            so.total_qty AS so_quantity,
            COALESCE(sa.completed_units, 0) AS completed_units,
            COALESCE(sa.rejected_units, 0)  AS rejected_units,
            GREATEST(
                so.total_qty
                - COALESCE(sa.completed_units, 0)
                - COALESCE(sa.rejected_units, 0),
                0
            ) AS pending_units
        FROM `tabSales Order` so
        /* Only keep SOs that have at least one FG item matching the date filter */
        INNER JOIN (
            SELECT DISTINCT soi.parent
            FROM `tabSales Order Item` soi
            INNER JOIN `tabItem` itm ON itm.name = soi.item_code
            WHERE soi.custom_ex_fty_date IS NOT NULL
              AND itm.custom_select_master = 'Finished Goods'
              AND {date_pred}
        ) soi_ok ON soi_ok.parent = so.name

        /* Scan aggregation for the selected operation via Operation Map */
        LEFT JOIN (
            SELECT 
                tbc.sales_order,
                SUM(CASE 
                    WHEN isl.log_status = 'Completed'
                     AND isl.status IN ('Counted','Activated','Pass')
                    THEN pi.quantity ELSE 0 
                END) AS completed_units,
                COUNT(CASE 
                    WHEN isl.log_status = 'Completed'
                     AND isl.status IN ('QC Reject','QC Recut','SP Recut','SP Reject')
                    THEN 1
                END) AS rejected_units
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor 
                ON tor.name = tbc.parent
            INNER JOIN `tabOperation Map` opm 
                ON opm.parent = tor.name 
               AND opm.operation = %(op)s
            INNER JOIN `tabProduction Item` pi 
                ON pi.tracking_order = tor.name 
               AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc 
                ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl 
                ON isl.production_item = pi.name 
               AND isl.operation = opm.operation
            WHERE 
                tbc.parentfield = 'component_bundle_configurations'
                AND tbc.sales_order IS NOT NULL
            GROUP BY tbc.sales_order
        ) sa ON sa.sales_order = so.name

        WHERE so.docstatus = 1
        HAVING so_quantity > 0
        ORDER BY so.name
        """,
        params,
        as_dict=True,
    )



def get_summary_wo(filters):
    """Per-Work Order summary for a selected operation (dup-safe)."""
    if not filters.get("operation"):
        return []

    params = {"op": filters["operation"]}
    # Build SOI date filter once
    if filters.get("date_range"):
        start, end = filters["date_range"]
        params.update({"start": start, "end": end})
        date_pred = "DATE(soi.custom_ex_fty_date) BETWEEN %(start)s AND %(end)s"
    else:
        from frappe.utils import now_datetime
        params["year"] = now_datetime().year
        date_pred = "YEAR(soi.custom_ex_fty_date) = %(year)s"

    return frappe.db.sql(
        f"""
        SELECT
            wo.name AS wo_number,
            wo.qty  AS wo_quantity,
            COALESCE(sa.completed_units, 0) AS completed_units,
            COALESCE(sa.rejected_units, 0)  AS rejected_units,
            GREATEST(
                wo.qty
                - COALESCE(sa.completed_units, 0)
                - COALESCE(sa.rejected_units, 0),
                0
            ) AS pending_units
        FROM `tabWork Order` wo

        /* WO → SO mapping (unique) */
        INNER JOIN (
            SELECT parent AS work_order, sales_order
            FROM `tabWork Order Sales Orders`
            WHERE sales_order IS NOT NULL
            GROUP BY parent, sales_order
        ) woso ON woso.work_order = wo.name

        /* DISTINCT (SO, item_code) that pass FG + date; tie to WO's item */
        INNER JOIN (
            SELECT DISTINCT soi.parent AS sales_order, soi.item_code
            FROM `tabSales Order Item` soi
            INNER JOIN `tabItem` itm ON itm.name = soi.item_code
            WHERE soi.custom_ex_fty_date IS NOT NULL
              AND itm.custom_select_master = 'Finished Goods'
              AND {date_pred}
        ) soi_ok ON soi_ok.sales_order = woso.sales_order
                AND soi_ok.item_code   = wo.production_item

        /* Scan aggregation for the selected operation via Operation Map */
        LEFT JOIN (
            SELECT 
                tbc.work_order,
                SUM(CASE 
                    WHEN isl.log_status = 'Completed'
                     AND isl.status IN ('Counted','Activated','Pass')
                    THEN pi.quantity ELSE 0 
                END) AS completed_units,
                COUNT(CASE 
                    WHEN isl.log_status = 'Completed'
                     AND isl.status IN ('QC Reject','QC Recut','SP Recut','SP Reject')
                    THEN 1
                END) AS rejected_units
            FROM `tabTracking Order Bundle Configuration` tbc
            INNER JOIN `tabTracking Order` tor 
                ON tor.name = tbc.parent
            INNER JOIN `tabOperation Map` opm 
                ON opm.parent = tor.name 
               AND opm.operation = %(op)s
            INNER JOIN `tabProduction Item` pi 
                ON pi.tracking_order = tor.name 
               AND pi.bundle_configuration = tbc.name
            INNER JOIN `tabTracking Component` tc 
                ON tc.name = pi.component AND tc.is_main = 1
            INNER JOIN `tabItem Scan Log` isl 
                ON isl.production_item = pi.name 
               AND isl.operation = opm.operation
            WHERE 
                tbc.parentfield = 'component_bundle_configurations'
                AND tbc.work_order IS NOT NULL
            GROUP BY tbc.work_order
        ) sa ON sa.work_order = wo.name

        WHERE wo.docstatus = 1
        HAVING wo_quantity > 0
        ORDER BY wo.name
        """,
        params,
        as_dict=True,
    )


def get_detail_so(so_name):
    if not so_name:
        return {}

    conds = ["so.name = %(so_name)s", "so.docstatus = 1"]
    params = {"so_name": so_name}

    # Get SO details (unchanged)
    so_details = frappe.db.sql(f"""
        SELECT 
            so.name AS so_number,
            so.total_qty AS so_quantity,
            GROUP_CONCAT(DISTINCT DATE(soi.custom_ex_fty_date) ORDER BY soi.item_code SEPARATOR ' | ') AS ex_factory_date,
            GROUP_CONCAT(DISTINCT itm.brand ORDER BY itm.item_name SEPARATOR ' | ') AS fty_client,
            GROUP_CONCAT(DISTINCT itm.item_name ORDER BY itm.item_name SEPARATOR ' | ') AS product_family,
            GROUP_CONCAT(DISTINCT itm.name ORDER BY itm.item_name SEPARATOR ' | ') AS fty_prod_id,
            GROUP_CONCAT(DISTINCT itm.name ORDER BY itm.item_name SEPARATOR ' | ') AS style,
            GROUP_CONCAT(DISTINCT itm.custom_colour_code ORDER BY itm.item_name SEPARATOR ' | ') AS color,
            GROUP_CONCAT(DISTINCT itm.custom_material_composition ORDER BY itm.item_name SEPARATOR ' | ') AS material
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        INNER JOIN `tabItem` itm ON itm.name = soi.item_code AND itm.custom_select_master = 'Finished Goods'
        WHERE { ' AND '.join(conds) }
        GROUP BY so.name, so.total_qty
    """, params, as_dict=True)

    if not so_details:
        frappe.msgprint("No Sales Order details found or not an FG Item")
        return {} 
    
    # Get metrics by operation and size — WITH Operation Map
    metrics_by_op = frappe.db.sql(f"""
        SELECT
            opm.operation,
            soi.custom_size AS size,
            SUM(soi.qty)    AS size_qty,
            COALESCE(ca.completed_units, 0) AS completed_units,
            COALESCE(ra.rejected_units, 0)  AS rejected_units
        FROM `tabSales Order` so

        /* de-dup SOI at (SO, item, ex_fty, size) */
        INNER JOIN (
            SELECT parent, item_code, custom_ex_fty_date, custom_size, SUM(qty) AS qty
            FROM `tabSales Order Item`
            GROUP BY parent, item_code, custom_ex_fty_date, custom_size
        ) soi ON soi.parent = so.name

        INNER JOIN `tabItem` itm
                ON itm.name = soi.item_code
            AND itm.custom_select_master = 'Finished Goods'

        INNER JOIN `tabTracking Order Bundle Configuration` tbc
                ON tbc.sales_order = so.name
            AND tbc.size = soi.custom_size
            AND tbc.parentfield = 'component_bundle_configurations'

        INNER JOIN `tabTracking Order` tor
                ON tor.name = tbc.parent

        /* de-dup Operation Map per (order, operation) */
        INNER JOIN (
            SELECT parent, operation
            FROM `tabOperation Map`
            GROUP BY parent, operation
        ) opm ON opm.parent = tor.name

        /* ==== Completed (sum each PI once per op+size) ==== */
        LEFT JOIN (
            SELECT
                x.operation,
                x.size,
                SUM(x.qty_once) AS completed_units
            FROM (
                SELECT
                    pc.operation,
                    pc.size,
                    pc.pi_name,
                    MAX(pc.pi_qty) AS qty_once
                FROM (
                    /* core PI rows per (op, size, PI) for the order */
                    SELECT
                        tor.name      AS tracking_order,
                        tbc.size      AS size,
                        opm2.operation AS operation,
                        pi.name       AS pi_name,
                        pi.quantity   AS pi_qty
                    FROM `tabSales Order` so2
                    INNER JOIN (
                        SELECT parent, item_code, custom_ex_fty_date, custom_size, SUM(qty) AS qty
                        FROM `tabSales Order Item`
                        GROUP BY parent, item_code, custom_ex_fty_date, custom_size
                    ) soi2 ON soi2.parent = so2.name
                    INNER JOIN `tabItem` itm2
                            ON itm2.name = soi2.item_code
                        AND itm2.custom_select_master = 'Finished Goods'
                    INNER JOIN `tabTracking Order Bundle Configuration` tbc
                            ON tbc.sales_order = so2.name
                        AND tbc.size = soi2.custom_size
                        AND tbc.parentfield = 'component_bundle_configurations'
                    INNER JOIN `tabTracking Order` tor
                            ON tor.name = tbc.parent
                    INNER JOIN (
                        SELECT parent, operation
                        FROM `tabOperation Map`
                        GROUP BY parent, operation
                    ) opm2 ON opm2.parent = tor.name
                    LEFT  JOIN `tabProduction Item` pi
                            ON pi.tracking_order = tor.name
                        AND pi.bundle_configuration = tbc.name
                    LEFT  JOIN `tabTracking Component` tc
                            ON tc.name = pi.component AND tc.is_main = 1
                    WHERE so2.docstatus = 1
                    AND so2.name = 'OCN00168'
                ) pc
                /* keep only PIs that have ANY good scan at that operation */
                INNER JOIN (
                    SELECT production_item, operation
                    FROM `tabItem Scan Log`
                    WHERE log_status = 'Completed'
                    AND status IN ('Counted','Activated','Pass')
                    GROUP BY production_item, operation
                ) good ON good.production_item = pc.pi_name
                    AND good.operation       = pc.operation
                GROUP BY pc.operation, pc.size, pc.pi_name
            ) x
            GROUP BY x.operation, x.size
        ) ca
        ON ca.operation = opm.operation
        AND ca.size      = soi.custom_size

        /* ==== Rejects (sum reject_count per op+size) ==== */
        LEFT JOIN (
            SELECT
                pc.operation,
                pc.size,
                SUM(COALESCE(rj.reject_count, 0)) AS rejected_units
            FROM (
                SELECT
                    tor.name      AS tracking_order,
                    tbc.size      AS size,
                    opm2.operation AS operation,
                    pi.name       AS pi_name
                FROM `tabSales Order` so2
                INNER JOIN (
                    SELECT parent, item_code, custom_ex_fty_date, custom_size, SUM(qty) AS qty
                    FROM `tabSales Order Item`
                    GROUP BY parent, item_code, custom_ex_fty_date, custom_size
                ) soi2 ON soi2.parent = so2.name
                INNER JOIN `tabItem` itm2
                        ON itm2.name = soi2.item_code
                    AND itm2.custom_select_master = 'Finished Goods'
                INNER JOIN `tabTracking Order Bundle Configuration` tbc
                        ON tbc.sales_order = so2.name
                    AND tbc.size = soi2.custom_size
                    AND tbc.parentfield = 'component_bundle_configurations'
                INNER JOIN `tabTracking Order` tor
                        ON tor.name = tbc.parent
                INNER JOIN (
                    SELECT parent, operation
                    FROM `tabOperation Map`
                    GROUP BY parent, operation
                ) opm2 ON opm2.parent = tor.name
                LEFT  JOIN `tabProduction Item` pi
                        ON pi.tracking_order = tor.name
                    AND pi.bundle_configuration = tbc.name
                LEFT  JOIN `tabTracking Component` tc
                        ON tc.name = pi.component AND tc.is_main = 1
                WHERE so2.docstatus = 1
                AND so2.name = 'OCN00168'
            ) pc
            LEFT JOIN (
                SELECT production_item, operation, COUNT(*) AS reject_count
                FROM `tabItem Scan Log`
                WHERE log_status = 'Completed'
                AND status IN ('QC Reject','QC Recut','SP Recut','SP Reject')
                GROUP BY production_item, operation
            ) rj
            ON rj.production_item = pc.pi_name
            AND rj.operation       = pc.operation
            GROUP BY pc.operation, pc.size
        ) ra
        ON ra.operation = opm.operation
        AND ra.size      = soi.custom_size

        WHERE {' AND '.join(conds)} 
        GROUP BY opm.operation, soi.custom_size
        ORDER BY opm.operation, soi.custom_size;

    """, params, as_dict=True)

    for row in metrics_by_op:
        row.pending_units = row.size_qty - (row.completed_units or 0) - (row.rejected_units or 0)

    return {
        "details": so_details[0],
        "metrics_by_op": metrics_by_op
    }


def get_detail_wo(wo_name):
    if not wo_name:
        return {}

    conds = ["wo.name = %(wo_name)s", "wo.docstatus = 1"]
    params = {"wo_name": wo_name}

    # Get WO details (unchanged)
    wo_details = frappe.db.sql(f"""
        SELECT 
            wo.name AS wo_number,
            wo.qty AS wo_quantity,        
            GROUP_CONCAT(DISTINCT woli.sales_order ORDER BY woli.sales_order SEPARATOR ' | ') AS sales_order,
            GROUP_CONCAT(DISTINCT CONVERT(woli.wo_allocated_qty, SIGNED) ORDER BY woli.sales_order SEPARATOR ' | ') AS wo_allocated_qty,
            GROUP_CONCAT(DISTINCT DATE(soi.custom_ex_fty_date) ORDER BY woli.sales_order SEPARATOR ' | ') AS ex_factory_date,
            GROUP_CONCAT(DISTINCT itm.brand ORDER BY woli.sales_order SEPARATOR ' | ') AS fty_client,
            GROUP_CONCAT(DISTINCT itm.item_name ORDER BY woli.sales_order SEPARATOR ' | ') AS product_family,
            GROUP_CONCAT(DISTINCT itm.name ORDER BY woli.sales_order SEPARATOR ' | ') AS fty_prod_id,
            GROUP_CONCAT(DISTINCT itm.name ORDER BY woli.sales_order SEPARATOR ' | ') AS style,
            GROUP_CONCAT(DISTINCT itm.custom_colour_code ORDER BY woli.sales_order SEPARATOR ' | ') AS color,
            GROUP_CONCAT(DISTINCT itm.custom_material_composition ORDER BY woli.sales_order SEPARATOR ' | ') AS material
        FROM `tabWork Order` wo
        INNER JOIN (
            SELECT parent AS work_order, sales_order, SUM(work_order_allocated_qty) as 'wo_allocated_qty'
            FROM `tabWork Order Line Item`
            GROUP BY parent, sales_order
        ) woli ON woli.work_order = wo.name
        INNER JOIN (
            SELECT parent, custom_ex_fty_date, item_code
            FROM `tabSales Order Item`
            GROUP BY parent, custom_ex_fty_date, item_code
        ) soi ON soi.parent = woli.sales_order AND soi.item_code = wo.production_item
        INNER JOIN `tabItem` itm ON itm.name = wo.production_item AND itm.custom_select_master = 'Finished Goods'
        WHERE {' AND '.join(conds)}
        GROUP BY wo.name, wo.qty
    """, params, as_dict=True)

    if not wo_details:
        frappe.msgprint("No Work Order details found or not an FG Item")
        return {}

    # Get metrics by operation and size — WITH Operation Map
    metrics_by_op = frappe.db.sql(f"""
        SELECT 
            opm.operation,  -- ✅ From Operation Map
            woli.size,
            SUM(woli.qty) AS size_qty,
            COALESCE(SUM(CASE 
                WHEN isl.status IN ('Counted','Activated','Pass') 
                THEN pi.quantity ELSE 0 END), 0) AS completed_units,
            COALESCE(COUNT(CASE 
                WHEN isl.status IN ('QC Reject','QC Recut','SP Recut','SP Reject') 
                THEN 1 END), 0) AS rejected_units
        FROM `tabWork Order` wo
        INNER JOIN (
            SELECT parent, size, work_order_allocated_qty AS qty
            FROM `tabWork Order Line Item`
            GROUP BY parent, size
        ) woli ON woli.parent = wo.name
        INNER JOIN `tabTracking Order Bundle Configuration` tbc 
            ON tbc.work_order = wo.name 
            AND tbc.size = woli.size
            AND tbc.parentfield = 'component_bundle_configurations'
        INNER JOIN `tabTracking Order` tor ON tor.name = tbc.parent
        INNER JOIN `tabOperation Map` opm ON opm.parent = tor.name  -- ✅ Join Operation Map
        INNER JOIN `tabItem` itm ON itm.name = wo.production_item AND itm.custom_select_master = 'Finished Goods'
        LEFT JOIN `tabProduction Item` pi 
            ON pi.tracking_order = tor.name 
            AND pi.bundle_configuration = tbc.name
        LEFT JOIN `tabTracking Component` tc 
            ON tc.name = pi.component AND tc.is_main = 1
        LEFT JOIN `tabItem Scan Log` isl 
            ON isl.production_item = pi.name 
            AND isl.log_status = 'Completed'
            AND isl.operation = opm.operation  -- ✅ Match mapped operation
        WHERE {' AND '.join(conds)}
        GROUP BY opm.operation, woli.size
        ORDER BY opm.operation, woli.size
    """, params, as_dict=True)

    for row in metrics_by_op:
        row.pending_units = row.size_qty - (row.completed_units or 0) - (row.rejected_units or 0)

    return {
        "details": wo_details[0],
        "metrics_by_op": metrics_by_op
    }