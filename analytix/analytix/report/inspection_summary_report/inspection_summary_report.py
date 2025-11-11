# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _

FABRIC_DTYPE = "Fabric Inspection"
TRIMS_DTYPE  = "Trims Inspection"
STATUS_FIELD = "inspection_status"   # common field in both doctypes

def execute(filters=None):
    filters = filters or {}

    fabric_counts = get_status_counts(FABRIC_DTYPE, filters)
    trims_counts  = get_status_counts(TRIMS_DTYPE,  filters)
    all_statuses = sorted(set(fabric_counts.keys()) | set(trims_counts.keys()))

    columns = get_columns()
    data = []
    for st in all_statuses:
        f = fabric_counts.get(st, 0)
        t = trims_counts.get(st, 0)
        data.append({"status": st, "fabric_count": f, "trims_count": t, "total": f + t})

    summary = build_tiles(fabric_counts, trims_counts)
    message = build_message_table(fabric_counts, trims_counts)

    # IMPORTANT: return no single chart; JS will render two pies
    return columns, data, message, None, summary


# ------------------------------ Data helpers ------------------------------

def get_status_counts(doctype, filters):
    where, vals = ["docstatus < 2"], {}

    if filters.get("company") and frappe.db.has_column(doctype, "company"):
        where.append("company = %(company)s")
        vals["company"] = filters["company"]

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
    return {(r.status or "Not Set"): int(r.cnt or 0) for r in rows}

def pick_date_column(doctype: str) -> str:
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
        ) or f"<tr><td colspan='2' style='padding:6px 8px; color:#6b7280'>{_('No records')}</td></tr>"
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

    # Include two chart holders; JS will render pies here
    html = f"""
    <div style="display:flex; flex-wrap:wrap; gap:24px; align-items:flex-start; margin:8px 0 6px 0;">
      {table_html(_("Fabric Summary"), fabric_counts)}
      {table_html(_("Trims Summary"), trims_counts)}
    </div>
    <div style="display:flex; flex-wrap:wrap; gap:24px; margin:8px 0;">
      <div style="flex:1 1 360px; min-width:320px;">
        <h6 style="margin:0 0 6px 0; color:#6b7280;">{_('Fabric: Status Split')}</h6>
        <div id="cx-fabric-pie"></div>
      </div>
      <div style="flex:1 1 360px; min-width:320px;">
        <h6 style="margin:0 0 6px 0; color:#6b7280;">{_('Trims: Status Split')}</h6>
        <div id="cx-trims-pie"></div>
      </div>
    </div>
    """
    return html
