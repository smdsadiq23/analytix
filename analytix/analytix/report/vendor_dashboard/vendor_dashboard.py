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
            "width": 140,
        },
    ]


def get_data(filters):
    conditions = get_conditions(filters)

    # Step 1: All outsourced operations across submitted CKPs
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
            AND ckp.docstatus = 1
            {conditions}
        ORDER BY
            ops.supplier
        """.format(conditions=conditions),
        filters or {},
        as_dict=True,
    )

    if not outsourced:
        return []

    # Step 2: Fetch operation map for all relevant CKPs
    ckp_names = list({r.ckp_name for r in outsourced})
    op_map_rows = frappe.db.sql(
        """
        SELECT
            parent      AS ckp_name,
            operation,
            next_operation,
            sequence_no
        FROM
            `tabOperation Map`
        WHERE
            parent IN ({placeholders})
        ORDER BY
            parent, sequence_no
        """.format(placeholders=", ".join(["%s"] * len(ckp_names))),
        ckp_names,
        as_dict=True,
    )

    # Build per-CKP lookup: { ckp_name: { operation: { prev_operation, next_operation } } }
    ckp_op_map = {}
    for row in op_map_rows:
        ckp_op_map.setdefault(row.ckp_name, {})[row.operation] = {
            "next_operation": row.next_operation,
            "sequence_no": row.sequence_no,
        }

    for ckp_name, ops in ckp_op_map.items():
        seq_to_op = {v["sequence_no"]: k for k, v in ops.items()}
        for details in ops.values():
            details["prev_operation"] = seq_to_op.get(details["sequence_no"] - 1, "")

    # Step 3: Group by supplier, collecting sales orders and (ckp, prev_op, next_op) tuples
    supplier_data = {}
    for row in outsourced:
        op_details = ckp_op_map.get(row.ckp_name, {}).get(row.operation, {})

        entry = supplier_data.setdefault(
            row.supplier,
            {"supplier": row.supplier, "sales_orders": set(), "ckp_ops": []},
        )
        entry["sales_orders"].add(row.sales_order)
        entry["ckp_ops"].append(
            {
                "ckp_name": row.ckp_name,
                "prev_op": op_details.get("prev_operation", ""),
                "next_op": op_details.get("next_operation", ""),
            }
        )

    # Step 4: For each supplier+CKP, sum bundle_qty via Item Scan Log
    #   Total Sent     = bundle_qty where scan log operation = prev_op of outsourced op
    #   Total Received = bundle_qty where scan log operation = next_op of outsourced op
    result = []

    for supplier, info in sorted(supplier_data.items()):
        total_sent = 0
        total_received = 0

        for ckp_op in info["ckp_ops"]:
            ckp_name = ckp_op["ckp_name"]
            prev_op  = ckp_op["prev_op"]
            next_op  = ckp_op["next_op"]

            if prev_op:
                sent = frappe.db.sql(
                    """
                    SELECT COALESCE(SUM(bd.bundle_qty), 0) AS qty
                    FROM
                        `tabCut Kit Plan Bundle Details` bd
                    INNER JOIN
                        `tabItem Scan Log` isl ON isl.production_item = bd.production_item_id
                    WHERE
                        bd.parent        = %s
                        AND isl.operation  = %s
                        AND isl.status     = 'Counted'
                        AND isl.log_status = 'Completed'
                    """,
                    (ckp_name, prev_op),
                    as_dict=True,
                )
                total_sent += sent[0].qty if sent else 0

            if next_op:
                received = frappe.db.sql(
                    """
                    SELECT COALESCE(SUM(bd.bundle_qty), 0) AS qty
                    FROM
                        `tabCut Kit Plan Bundle Details` bd
                    INNER JOIN
                        `tabItem Scan Log` isl ON isl.production_item = bd.production_item_id
                    WHERE
                        bd.parent        = %s
                        AND isl.operation  = %s
                        AND isl.status     = 'Counted'
                        AND isl.log_status = 'Completed'
                    """,
                    (ckp_name, next_op),
                    as_dict=True,
                )
                total_received += received[0].qty if received else 0

        result.append(
            {
                "supplier": supplier,
                "no_of_ocns": len(info["sales_orders"]),
                "total_sent": int(total_sent),
                "total_received": int(total_received),
            }
        )

    return result


def get_conditions(filters):
    conditions = []

    if filters:
        if filters.get("supplier"):
            conditions.append("AND ops.supplier = %(supplier)s")

        if filters.get("from_date"):
            conditions.append("AND ckp.creation >= %(from_date)s")

        if filters.get("to_date"):
            conditions.append("AND ckp.creation <= %(to_date)s")

    return " ".join(conditions)