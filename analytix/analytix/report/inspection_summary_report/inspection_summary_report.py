# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from collections import defaultdict

FABRIC_DT = "Fabric Inspection"
TRIMS_DT  = "Trims Inspection"
STATUS_FIELD = "inspection_status"
DATE_FIELD   = "creation"

def execute(filters=None):
    filters = filters or {}

    # Build counts per status for both doctypes
    fabric_counts = get_counts(FABRIC_DT, filters)
    trims_counts  = get_counts(TRIMS_DT,  filters)

    # Union of all statuses observed
    all_statuses = sorted(set(fabric_counts.keys()) | set(trims_counts.keys()))

    columns = get_columns()
    data = []
    for st in all_statuses:
        fc = int(fabric_counts.get(st, 0))
        tc = int(trims_counts.get(st, 0))
        data.append({
            "status": st,
            "fabric_count": fc,
            "trims_count": tc,
            "total": fc + tc,
        })

    # Summary tiles (remove Fabric: In Progress as requested)
    summary = build_tiles(fabric_counts, trims_counts)

    # Return no built-in chart; the report JS will render TWO pies (fabric + trims)
    chart = None

    return columns, data, None, summary

# ----------------------------------------------------------------------

def get_columns():
    return [
        {"label": _("Status"),         "fieldname": "status",        "fieldtype": "Data", "width": 180},
        {"label": _("Fabric Inspection Count"), "fieldname": "fabric_count", "fieldtype": "Int",  "width": 220},
        {"label": _("Trims Inspection Count"),  "fieldname": "trims_count",  "fieldtype": "Int",  "width": 220},
        {"label": _("Total"),          "fieldname": "total",         "fieldtype": "Int",  "width": 120},
    ]

def get_counts(doctype, filters):
    """
    Returns a dict {status: count} for the given doctype.
    Applies optional filters:
      - company (if the field exists on the doctype)
      - from_date / to_date over DATE_FIELD (defaults to 'creation')
    """
    conds = ["docstatus < 2"]  # include Draft/Submitted; exclude Cancelled
    vals = {}

    # company filter (only if column exists)
    if filters.get("company") and frappe.db.has_column(doctype, "company"):
        conds.append("company = %(company)s")
        vals["company"] = filters["company"]

    # date range (on DATE_FIELD)
    if filters.get("from_date"):
        conds.append(f"DATE({DATE_FIELD}) >= %(from_date)s")
        vals["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conds.append(f"DATE({DATE_FIELD}) <= %(to_date)s")
        vals["to_date"] = filters["to_date"]

    # group by status; tolerate missing/empty status values
    where_sql = " AND ".join(conds) if conds else "1=1"
    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE({STATUS_FIELD}, 'Not Set') AS status,
            COUNT(*) AS cnt
        FROM `tab{doctype}`
        WHERE {where_sql}
        GROUP BY COALESCE({STATUS_FIELD}, 'Not Set')
        """,
        vals,
        as_dict=True,
    )

    out = defaultdict(int)
    for r in rows:
        out[r["status"]] += int(r["cnt"] or 0)
    return dict(out)

def status_color(status):
    s = (status or "").lower()
    if "accept" in s or "pass" in s:
        return "green"
    if "reject" in s or "fail" in s:
        return "red"
    if "draft" in s:
        return "blue"
    if "submit" in s:
        return "gray"
    if "progress" in s:
        return "orange"
    return "blue"

def build_tiles(fabric_counts, trims_counts):
    def pack(title, total, color):
        return {"label": title, "value": int(total), "indicator": color, "datatype": "Int"}

    f_total = sum(fabric_counts.values())
    t_total = sum(trims_counts.values())

    tiles = [
        pack(_("Fabric: Total"), f_total, "blue"),
        pack(_("Trims: Total"),  t_total, "blue"),
    ]

    # Per-status tiles (requested to remove ONLY "Fabric: In Progress")
    for st, cnt in sorted(fabric_counts.items()):
        if st.strip().lower() == "in progress":
            continue  # skip this one for Fabric
        tiles.append(pack(_("Fabric: ") + st, cnt, status_color(st)))

    for st, cnt in sorted(trims_counts.items()):
        # keep all trims statuses (including In Progress)
        tiles.append(pack(_("Trims: ") + st, cnt, status_color(st)))

    return tiles
