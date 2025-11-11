# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _

FABRIC_DTYPE = "Fabric Inspection"
TRIMS_DTYPE  = "Trims Inspection"
STATUS_FIELD = "inspection_status"   # common field in both doctypes

def execute(filters=None):
    filters = filters or {}
    chart_view = (filters.get("chart_view") or "Fabric").strip()

    # Pull counts with filters applied per doctype
    fabric_counts = get_status_counts(FABRIC_DTYPE, filters)
    trims_counts  = get_status_counts(TRIMS_DTYPE,  filters)

    all_statuses = sorted(set(fabric_counts.keys()) | set(trims_counts.keys()))

    columns = get_columns()
    data = []
    for st in all_statuses:
        f = fabric_counts.get(st, 0)
        t = trims_counts.get(st, 0)
        data.append({
            "status": st,
            "fabric_count": f,
            "trims_count": t,
            "total": f + t,
        })

    summary = build_tiles(fabric_counts, trims_counts)
    message = build_message_table(fabric_counts, trims_counts)
    chart   = build_chart(chart_view, all_statuses, fabric_counts, trims_counts)

    # Return (columns, result rows, message, chart, report_summary tiles)
    return columns, data, message, chart, summary


# ------------------------------ Data helpers ------------------------------

def get_status_counts(doctype, filters):
    """
    Returns {status: count} for the given doctype,
    applying Company / From / To date filters when those columns exist.
    """
    where, vals = ["docstatus < 2"], {}

    # Company filter (only if column exists on the doctype)
    if filters.get("company") and frappe.db.has_column(doctype, "company"):
        where.append("company = %(company)s")
        vals["company"] = filters["company"]

    # Date column detection per doctype
    date_col = pick_date_column(doctype)
    if filters.get("from_date"):
        where.append(f"DATE(`{date_col}`) >= %(from_date)s")
        vals["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        where.append(f"DATE(`{date_col}`) <= %(to_date)s")
        vals["to_date"] = filters["to_date"]

    sql = f"""
        SELECT {STATUS_FIELD} AS status, COUNT(*) AS cnt
        FROM `tab{doctype}`
        WHERE {" AND ".join(where)}
        GROUP BY {STATUS_FIELD}
    """
    rows = frappe.db.sql(sql, vals, as_dict=True)
    # Normalize null/empty status to "Not Set"
    return { (r.status or "Not Set"): int(r.cnt or 0) for r in rows }


def pick_date_column(doctype: str) -> str:
    """
    Choose a reasonable date column for filtering per doctype.
    Preference order:
      inspection_date, posting_date, date, transaction_date, modified, creation
    Falls back to 'creation' if none exist.
    """
    for col in ("inspection_date", "posting_date", "date", "transaction_date", "modified", "creation"):
        if frappe.db.has_column(doctype, col):
            return col
    return "creation"


# ------------------------------ Grid ------------------------------

def get_columns():
    return [
        {"label": _("Status"),        "fieldname": "status",        "fieldtype": "Data", "width": 180},
        {"label": _(FABRIC_DTYPE),    "fieldname": "fabric_count",  "fieldtype": "Int",  "width": 140},
        {"label": _(TRIMS_DTYPE),     "fieldname": "trims_count",   "fieldtype": "Int",  "width": 140},
        {"label": _("Total"),         "fieldname": "total",         "fieldtype": "Int",  "width": 120},
    ]


# ------------------------------ Tiles ------------------------------

def build_tiles(fabric_counts, trims_counts):
    def pack(title, total, color):
        return {"label": title, "value": total, "indicator": color, "datatype": "Int"}

    f_total = sum(fabric_counts.values())
    t_total = sum(trims_counts.values())

    key_statuses = ["Pass", "Fail", "Pending", "In Progress", "Not Set"]

    tiles = [
        pack(_("Fabric: Total"), f_total, "blue"),
        pack(_("Trims: Total"),  t_total, "blue"),
    ]

    for st in key_statuses:
        if st in fabric_counts:
            tiles.append(pack(_("Fabric: ") + st, fabric_counts.get(st, 0), status_color(st)))
    for st in key_statuses:
        if st in trims_counts:
            tiles.append(pack(_("Trims: ") + st, trims_counts.get(st, 0), status_color(st)))

    return tiles


def status_color(status):
    s = (status or "").lower()
    if "pass" in s or "ok" in s or "accepted" in s:
        return "green"
    if "fail" in s or "reject" in s:
        return "red"
    if "pending" in s or "hold" in s or "wip" in s or "progress" in s:
        return "orange"
    return "gray"


# ------------------------------ Message HTML ------------------------------

def build_message_table(fabric_counts, trims_counts):
    def table_html(title, counts):
        rows = "".join(
            f"<tr><td style='padding:4px 8px'>{frappe.as_unicode(st)}</td>"
            f"<td style='padding:4px 8px; text-align:right'>{cnt}</td></tr>"
            for st, cnt in sorted(counts.items())
        )
        if not rows:
            rows = f"<tr><td colspan='2' style='padding:6px 8px; color:#6b7280'>{_('No records')}</td></tr>"
        return f"""
        <div style="margin: 0 0 12px 0;">
          <h6 style="margin:0 0 6px 0; color:#6b7280;">{frappe.as_unicode(title)}</h6>
          <table class="table table-bordered" style="width:auto; min-width:280px">
            <thead>
              <tr>
                <th style="padding:4px 8px">{_('Status')}</th>
                <th style="padding:4px 8px; text-align:right">{_('Count')}</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """

    html = """
    <div style="display:flex; flex-wrap:wrap; gap:24px; align-items:flex-start; margin:8px 0 6px 0;">
      {fabric_tbl}
      {trims_tbl}
    </div>
    """.format(
        fabric_tbl=table_html(_("Fabric Summary"), fabric_counts),
        trims_tbl=table_html(_("Trims Summary"), trims_counts),
    )
    return html


# ------------------------------ Chart ------------------------------

def build_chart(chart_view, statuses, fabric_counts, trims_counts):
    """
    Returns a Frappe report chart object.
    - Fabric  -> pie (fabric only)
    - Trims   -> pie (trims only)
    - Combined Bar -> bar comparing both
    """
    chart_view = (chart_view or "Fabric").lower()

    if chart_view == "trims":
        labels = statuses
        values = [trims_counts.get(st, 0) for st in labels]
        return {
            "data": {"labels": labels, "datasets": [{"name": _("Trims"), "values": values}]},
            "type": "pie",
            "height": 240,
        }

    if chart_view in ("combined bar", "combined", "both"):
        labels   = statuses
        f_values = [fabric_counts.get(st, 0) for st in labels]
        t_values = [trims_counts.get(st, 0) for st in labels]
        return {
            "data": {
                "labels": labels,
                "datasets": [
                    {"name": _("Fabric"), "values": f_values},
                    {"name": _("Trims"),  "values": t_values},
                ],
            },
            "type": "bar",
            "height": 260,
        }

    # default: Fabric pie
    labels = statuses
    values = [fabric_counts.get(st, 0) for st in labels]
    return {
        "data": {"labels": labels, "datasets": [{"name": _("Fabric"), "values": values}]},
        "type": "pie",
        "height": 240,
    }
