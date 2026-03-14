# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "Vendor Name",
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 220,
        },
        {
            "label": "No. of OCNs",
            "fieldname": "no_of_ocns",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": "Total Sent",
            "fieldname": "total_sent",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": "Total Received",
            "fieldname": "total_received",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": "Received %",
            "fieldname": "received_pct",
            "fieldtype": "Percent",
            "width": 120,
        },
        {
            "label": "Avg Lead Time (Days)",
            "fieldname": "avg_lead_time",
            "fieldtype": "Float",
            "precision": 1,
            "width": 160,
        },
        {
            "label": "Total Rejection",
            "fieldname": "total_rejection",
            "fieldtype": "Int",
            "width": 140,
        },
        {
            "label": "Rejection %",
            "fieldname": "rejection_pct",
            "fieldtype": "Percent",
            "width": 120,
        },
    ]


def get_data(filters):
    # ------------------------------------------------------------------ #
    # QUERY 1 — All outsourced operations from submitted CKPs              #
    # ------------------------------------------------------------------ #
    supplier_filter_sql = (
        "AND ops.supplier = %(supplier)s" if filters and filters.get("supplier") else ""
    )

    outsourced = frappe.db.sql(
        """
        SELECT
            ckp.name        AS ckp_name,
            ckp.sales_order,
            ops.supplier,
            ops.operation
        FROM
            `tabCut Kit Plan`       ckp
        INNER JOIN
            `tabCut Kit Operations` ops ON ops.parent = ckp.name
        WHERE
            ops.production_type = 'Outsourced'
            AND ops.supplier IS NOT NULL
            AND ops.supplier != ''
            AND ckp.docstatus  = 1
            {supplier_filter}
        """.format(supplier_filter=supplier_filter_sql),
        filters or {},
        as_dict=True,
    )

    if not outsourced:
        return []

    ckp_names = list({r.ckp_name for r in outsourced})

    # ------------------------------------------------------------------ #
    # QUERY 2 — Full operation map for all relevant CKPs in one shot       #
    # ------------------------------------------------------------------ #
    op_map_rows = frappe.db.sql(
        """
        SELECT parent AS ckp_name, operation, next_operation, sequence_no
        FROM   `tabOperation Map`
        WHERE  parent IN ({ph})
        ORDER  BY parent, sequence_no
        """.format(ph=", ".join(["%s"] * len(ckp_names))),
        ckp_names,
        as_dict=True,
    )

    # Build lookup: ckp_name → { operation → {prev_op, next_op} }
    ckp_op_map = defaultdict(dict)
    for row in op_map_rows:
        ckp_op_map[row.ckp_name][row.operation] = {
            "next_op": row.next_operation,
            "seq": row.sequence_no,
        }

    for ckp_name, ops in ckp_op_map.items():
        seq_to_op = {v["seq"]: k for k, v in ops.items()}
        for details in ops.values():
            details["prev_op"] = seq_to_op.get(details["seq"] - 1, "")

    # ------------------------------------------------------------------ #
    # Python — derive prev/next per outsourced row; build supplier map     #
    # ------------------------------------------------------------------ #
    # supplier_data: { supplier: { sales_orders: set, ckp_ops: list } }
    supplier_data = defaultdict(lambda: {"sales_orders": set(), "ckp_ops": []})

    # Also collect every (ckp_name, prev_op) and (ckp_name, next_op) we'll need
    for row in outsourced:
        op_detail = ckp_op_map.get(row.ckp_name, {}).get(row.operation, {})
        supplier_data[row.supplier]["sales_orders"].add(row.sales_order)
        supplier_data[row.supplier]["ckp_ops"].append(
            {
                "ckp_name": row.ckp_name,
                "prev_op": op_detail.get("prev_op", ""),
                "next_op": op_detail.get("next_op", ""),
            }
        )

    # ------------------------------------------------------------------ #
    # QUERY 3 — All bundle details for all CKPs in one shot                #
    # ------------------------------------------------------------------ #
    bundle_rows = frappe.db.sql(
        """
        SELECT parent AS ckp_name, production_item_id, bundle_qty
        FROM   `tabCut Kit Plan Bundle Details`
        WHERE  parent IN ({ph})
        """.format(ph=", ".join(["%s"] * len(ckp_names))),
        ckp_names,
        as_dict=True,
    )

    # bundle_qty_map: { (ckp_name, production_item_id) → bundle_qty }
    # production_item_id → ckp_name  (for scan log join)
    item_to_ckp   = {}   # production_item_id → ckp_name
    item_bundle   = {}   # production_item_id → bundle_qty

    for b in bundle_rows:
        item_to_ckp[b.production_item_id]  = b.ckp_name
        item_bundle[b.production_item_id]  = b.bundle_qty

    if not item_to_ckp:
        return []

    production_item_ids = list(item_to_ckp.keys())

    # ------------------------------------------------------------------ #
    # QUERY 4 — All matching Item Scan Log rows in one shot                #
    # ------------------------------------------------------------------ #
    date_clauses = []
    date_params  = []
    if filters:
        if filters.get("from_date"):
            date_clauses.append("AND DATE(isl.logged_time) >= %s")
            date_params.append(filters["from_date"])
        if filters.get("to_date"):
            date_clauses.append("AND DATE(isl.logged_time) <= %s")
            date_params.append(filters["to_date"])
    date_filter_sql = " ".join(date_clauses)

    scan_rows = frappe.db.sql(
        """
        SELECT
            production_item,
            operation,
            logged_time
        FROM
            `tabItem Scan Log`
        WHERE
            production_item IN ({ph})
            AND status     = 'Counted'
            AND log_status = 'Completed'
        """.format(ph=", ".join(["%s"] * len(production_item_ids))),
        production_item_ids,
        as_dict=True,
    )

    # ------------------------------------------------------------------ #
    # QUERY 5 — Rejection rows (Finish QC* operations, rejection statuses) #
    # ------------------------------------------------------------------ #
    REJECTION_STATUSES = (
        "QC Rejected", "SP Rejected"
    )

    rejection_rows = frappe.db.sql(
        """
        SELECT
            production_item,
            operation
        FROM
            `tabItem Scan Log`
        WHERE
            production_item IN ({ph})
            AND operation LIKE 'Finish QC%%'
            AND status IN ({st})
        """.format(
            ph=", ".join(["%s"] * len(production_item_ids)),
            st=", ".join(["%s"] * len(REJECTION_STATUSES)),
        ),
        production_item_ids + list(REJECTION_STATUSES),
        as_dict=True,
    )

    # rejection_index: { ckp_name → set(production_item_ids) }
    rejection_index = defaultdict(set)
    for r in rejection_rows:
        ckp = item_to_ckp.get(r.production_item)
        if ckp:
            rejection_index[ckp].add(r.production_item)

    # ------------------------------------------------------------------ #
    # Python — index scan log rows                                         #
    # scan_index: { (ckp_name, operation) → set of production_item_ids }  #
    # ------------------------------------------------------------------ #
    # We keep two indexes:
    #   scan_sent     — rows that also pass the date filter (for Sent)
    #   scan_received — all rows regardless of date (for Received)
    from datetime import date as date_type
    import datetime

    from_date = None
    to_date   = None
    if filters:
        if filters.get("from_date"):
            fd = filters["from_date"]
            from_date = fd if isinstance(fd, date_type) else datetime.datetime.strptime(str(fd), "%Y-%m-%d").date()
        if filters.get("to_date"):
            td = filters["to_date"]
            to_date = td if isinstance(td, date_type) else datetime.datetime.strptime(str(td), "%Y-%m-%d").date()

    # { (ckp_name, operation) → { pid: logged_time } }
    scan_sent_index     = defaultdict(dict)   # date-filtered
    scan_received_index = defaultdict(dict)   # no date filter

    for s in scan_rows:
        ckp = item_to_ckp.get(s.production_item)
        if not ckp:
            continue

        key      = (ckp, s.operation)
        log_time = s.logged_time

        # Received index — no date restriction
        scan_received_index[key][s.production_item] = log_time

        # Sent index — only if within date range
        log_date = log_time.date() if hasattr(log_time, "date") else log_time
        if from_date and log_date < from_date:
            continue
        if to_date and log_date > to_date:
            continue
        scan_sent_index[key][s.production_item] = log_time

    # ------------------------------------------------------------------ #
    # Python — aggregate per supplier                                      #
    # ------------------------------------------------------------------ #
    result = []

    for supplier, info in sorted(supplier_data.items()):
        total_sent      = 0
        total_received  = 0
        total_rejection = 0
        lead_time_days  = []

        for ckp_op in info["ckp_ops"]:
            ckp_name = ckp_op["ckp_name"]
            prev_op  = ckp_op["prev_op"]
            next_op  = ckp_op["next_op"]

            # sent_items: { pid: sent_logged_time }
            sent_items = scan_sent_index.get((ckp_name, prev_op), {}) if prev_op else {}

            for pid in sent_items:
                total_sent += item_bundle.get(pid, 0)

            if next_op and sent_items:
                # Only count received for items that were actually sent in the filtered window
                received_items = scan_received_index.get((ckp_name, next_op), {})
                common_pids = sent_items.keys() & received_items.keys()
                for pid in common_pids:
                    total_received += item_bundle.get(pid, 0)
                    # Lead time per item: received_time - sent_time (in days)
                    sent_dt     = sent_items[pid]
                    received_dt = received_items[pid]
                    delta = (received_dt - sent_dt).total_seconds() / 86400
                    lead_time_days.append(delta)

            # --- Total Rejection (Finish QC* with rejection status) ---
            rejected_pids = rejection_index.get(ckp_name, set()) & sent_items.keys()
            for pid in rejected_pids:
                total_rejection += len(rejected_pids)

        if filters and not total_sent:
            continue

        received_pct   = round(total_received / total_sent * 100, 2) if total_sent else 0
        avg_lead_time  = round(sum(lead_time_days) / len(lead_time_days), 1) if lead_time_days else 0
        rejection_pct  = round(total_rejection / total_sent * 100, 2) if total_sent else 0

        result.append(
            {
                "supplier":        supplier,
                "no_of_ocns":      len(info["sales_orders"]),
                "total_sent":      int(total_sent),
                "total_received":  int(total_received),
                "received_pct":    received_pct,
                "avg_lead_time":   avg_lead_time,
                "total_rejection": int(total_rejection),
                "rejection_pct":   rejection_pct,
            }
        )

    return result