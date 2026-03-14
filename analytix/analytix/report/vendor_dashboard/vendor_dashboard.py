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
            "label": "OCN",
            "fieldname": "sales_order",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 140,
        },
        {
            "label": "Vendor",
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 160,
        },
        {
            "label": "Style",
            "fieldname": "style",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": "Colour",
            "fieldname": "colour",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Size",
            "fieldname": "size",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": "Order Qty",
            "fieldname": "order_qty",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Sent",
            "fieldname": "total_sent",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": "Received",
            "fieldname": "total_received",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Balance",
            "fieldname": "balance",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": "Received %",
            "fieldname": "received_pct",
            "fieldtype": "Percent",
            "width": 110,
        },
        {
            "label": "Rejection",
            "fieldname": "total_rejection",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Rejection %",
            "fieldname": "rejection_pct",
            "fieldtype": "Percent",
            "width": 110,
        },
        {
            "label": "Sent Date",
            "fieldname": "sent_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Last Received Date",
            "fieldname": "last_received_date",
            "fieldtype": "Date",
            "width": 150,
        },
        {
            "label": "No. of Days",
            "fieldname": "no_of_days",
            "fieldtype": "Int",
            "width": 110,
        },
    ]


def get_data(filters):
    from datetime import date as date_type
    import datetime

    supplier_filter_sql = (
        "AND ops.supplier = %(supplier)s" if filters and filters.get("supplier") else ""
    )

    # ------------------------------------------------------------------ #
    # QUERY 1 — Outsourced operations from submitted CKPs                  #
    # ------------------------------------------------------------------ #
    outsourced = frappe.db.sql(
        """
        SELECT
            ckp.name        AS ckp_name,
            ckp.sales_order,
            ckp.style,
            ckp.colour,
            ops.supplier,
            ops.operation
        FROM
            `tabCut Kit Plan`       ckp
        INNER JOIN
            `tabCut Kit Operations` ops ON ops.parent = ckp.name
        WHERE
            ops.production_type = 'Outsourced'
            AND ops.supplier    IS NOT NULL
            AND ops.supplier    != ''
            AND ckp.docstatus   = 1
            {supplier_filter}
        ORDER BY
            ckp.sales_order, ops.supplier
        """.format(supplier_filter=supplier_filter_sql),
        filters or {},
        as_dict=True,
    )

    if not outsourced:
        return []

    ckp_names = list({r.ckp_name for r in outsourced})

    # ------------------------------------------------------------------ #
    # QUERY 2 — Operation map for all CKPs                                 #
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
    # QUERY 3 — Bundle summary (order qty per size per CKP)                #
    # ------------------------------------------------------------------ #
    summary_rows = frappe.db.sql(
        """
        SELECT parent AS ckp_name, size, SUM(quantity) AS order_qty
        FROM   `tabCut Kit Plan Item`
        WHERE  parent IN ({ph})
        GROUP  BY parent, size
        """.format(ph=", ".join(["%s"] * len(ckp_names))),
        ckp_names,
        as_dict=True,
    )
    # order_qty_map: { (ckp_name, size) → order_qty }
    order_qty_map = {(r.ckp_name, r.size): r.order_qty for r in summary_rows}

    # ------------------------------------------------------------------ #
    # QUERY 4 — Bundle details (production_item_id → ckp, size, qty)       #
    # ------------------------------------------------------------------ #
    bundle_rows = frappe.db.sql(
        """
        SELECT parent AS ckp_name, production_item_id, size, bundle_qty
        FROM   `tabCut Kit Plan Bundle Details`
        WHERE  parent IN ({ph})
        """.format(ph=", ".join(["%s"] * len(ckp_names))),
        ckp_names,
        as_dict=True,
    )

    item_to_ckp  = {}   # pid → ckp_name
    item_to_size = {}   # pid → size
    item_bundle  = {}   # pid → bundle_qty

    for b in bundle_rows:
        item_to_ckp[b.production_item_id]  = b.ckp_name
        item_to_size[b.production_item_id] = b.size
        item_bundle[b.production_item_id]  = b.bundle_qty

    if not item_to_ckp:
        return []

    production_item_ids = list(item_to_ckp.keys())

    # ------------------------------------------------------------------ #
    # QUERY 5 — Item Scan Log (sent + received)                            #
    # ------------------------------------------------------------------ #
    scan_rows = frappe.db.sql(
        """
        SELECT production_item, operation, logged_time
        FROM   `tabItem Scan Log`
        WHERE  production_item IN ({ph})
          AND  status     = 'Counted'
          AND  log_status = 'Completed'
        """.format(ph=", ".join(["%s"] * len(production_item_ids))),
        production_item_ids,
        as_dict=True,
    )

    # ------------------------------------------------------------------ #
    # QUERY 6 — Rejection rows                                             #
    # ------------------------------------------------------------------ #
    REJECTION_STATUSES = ("QC Rejected", "SP Rejected")

    rejection_rows = frappe.db.sql(
        """
        SELECT production_item
        FROM   `tabItem Scan Log`
        WHERE  production_item IN ({ph})
          AND  operation LIKE 'Finish QC%%'
          AND  status IN ({st})
        """.format(
            ph=", ".join(["%s"] * len(production_item_ids)),
            st=", ".join(["%s"] * len(REJECTION_STATUSES)),
        ),
        production_item_ids + list(REJECTION_STATUSES),
        as_dict=True,
    )

    # rejection_set: set of production_item_ids that were rejected
    rejection_set = {r.production_item for r in rejection_rows}

    # ------------------------------------------------------------------ #
    # Python — parse date filter                                           #
    # ------------------------------------------------------------------ #
    from_date = to_date = None
    if filters:
        if filters.get("from_date"):
            fd = filters["from_date"]
            from_date = fd if isinstance(fd, date_type) else datetime.datetime.strptime(str(fd), "%Y-%m-%d").date()
        if filters.get("to_date"):
            td = filters["to_date"]
            to_date = td if isinstance(td, date_type) else datetime.datetime.strptime(str(td), "%Y-%m-%d").date()

    # ------------------------------------------------------------------ #
    # Python — build scan indexes                                          #
    # { (ckp_name, operation) → { pid: logged_time } }                    #
    # ------------------------------------------------------------------ #
    scan_sent_index     = defaultdict(dict)   # date-filtered
    scan_received_index = defaultdict(dict)   # no date filter

    for s in scan_rows:
        ckp = item_to_ckp.get(s.production_item)
        if not ckp:
            continue
        key      = (ckp, s.operation)
        log_time = s.logged_time

        scan_received_index[key][s.production_item] = log_time

        log_date = log_time.date() if hasattr(log_time, "date") else log_time
        if from_date and log_date < from_date:
            continue
        if to_date and log_date > to_date:
            continue
        scan_sent_index[key][s.production_item] = log_time

    # ------------------------------------------------------------------ #
    # Python — build row key map from outsourced list                      #
    # row_key: (sales_order, supplier, style, colour, size)                #
    # ------------------------------------------------------------------ #
    # row_data: { row_key → { ckp_ops, fields } }
    row_data = {}

    for row in outsourced:
        op_detail = ckp_op_map.get(row.ckp_name, {}).get(row.operation, {})
        prev_op   = op_detail.get("prev_op", "")
        next_op   = op_detail.get("next_op", "")

        # Determine sizes from bundle summary for this CKP
        sizes = [
            size for (ckp, size) in order_qty_map.keys() if ckp == row.ckp_name
        ]

        for size in sizes:
            key = (row.sales_order, row.supplier, row.style, row.colour, size)
            if key not in row_data:
                row_data[key] = {
                    "sales_order": row.sales_order,
                    "supplier":    row.supplier,
                    "style":       row.style,
                    "colour":      row.colour,
                    "size":        size,
                    "order_qty":   order_qty_map.get((row.ckp_name, size), 0),
                    "ckp_ops":     [],
                }
            row_data[key]["ckp_ops"].append(
                {"ckp_name": row.ckp_name, "prev_op": prev_op, "next_op": next_op}
            )

    # ------------------------------------------------------------------ #
    # Python — aggregate per row                                           #
    # ------------------------------------------------------------------ #
    result = []

    for key, info in sorted(row_data.items()):
        total_sent      = 0
        total_received  = 0
        total_rejection = 0
        sent_dates      = []
        received_dates  = []
        size            = info["size"]

        for ckp_op in info["ckp_ops"]:
            ckp_name = ckp_op["ckp_name"]
            prev_op  = ckp_op["prev_op"]
            next_op  = ckp_op["next_op"]

            # Filter sent items to this size only
            all_sent = scan_sent_index.get((ckp_name, prev_op), {}) if prev_op else {}
            sent_items = {
                pid: t for pid, t in all_sent.items()
                if item_to_size.get(pid) == size
            }

            for pid, t in sent_items.items():
                total_sent += item_bundle.get(pid, 0)
                sent_dates.append(t)

            if next_op and sent_items:
                all_received = scan_received_index.get((ckp_name, next_op), {})
                for pid in sent_items.keys() & all_received.keys():
                    total_received += item_bundle.get(pid, 0)
                    received_dates.append(all_received[pid])

            # Rejections — intersection of sent items and rejection set
            for pid in sent_items.keys() & rejection_set:
                total_rejection += 1

        if filters and not total_sent:
            continue

        received_pct  = round(total_received / total_sent * 100, 2) if total_sent else 0
        rejection_pct = round(total_rejection / total_sent * 100, 2) if total_sent else 0
        balance       = total_received - total_sent

        sent_date          = min(t.date() if hasattr(t, "date") else t for t in sent_dates) if sent_dates else None
        last_received_date = max(t.date() if hasattr(t, "date") else t for t in received_dates) if received_dates else None
        no_of_days         = (last_received_date - sent_date).days if sent_date and last_received_date else 0

        result.append(
            {
                "sales_order":       info["sales_order"],
                "supplier":          info["supplier"],
                "style":             info["style"],
                "colour":            info["colour"],
                "size":              size,
                "order_qty":         int(info["order_qty"]),
                "total_sent":        int(total_sent),
                "total_received":    int(total_received),
                "balance":           int(balance),
                "received_pct":      received_pct,
                "total_rejection":   int(total_rejection),
                "rejection_pct":     rejection_pct,
                "sent_date":         sent_date,
                "last_received_date": last_received_date,
                "no_of_days":        no_of_days,
            }
        )

    return result