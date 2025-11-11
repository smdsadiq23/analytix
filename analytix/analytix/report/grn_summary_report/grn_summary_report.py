# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    message = get_message_table(data)
    summary = get_summary(data)
    # NOTE: Frappe script report return order:
    #   columns, result, message (HTML), chart (dict), report_summary (list)
    return columns, data, message, chart, summary

def get_columns():
    return [
        {"label": "Purchase Order", "fieldname": "purchase_order", "fieldtype": "Link", "options": "Purchase Order", "width": 150},
        {"label": "PO Date", "fieldname": "transaction_date", "fieldtype": "Date", "width": 100},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 120},
        {"label": "PO Status", "fieldname": "po_status", "fieldtype": "Data", "width": 150},
        {"label": "GRN Created", "fieldname": "grn_created", "fieldtype": "Data", "width": 120},
        {"label": "GRN Completed", "fieldname": "grn_completed", "fieldtype": "Data", "width": 120},
    ]

def get_data(filters):
    # Base conditions for PO
    po_conditions = ["po.docstatus = 1"]
    po_conditions.append("po.status IN ('To Receive and Bill', 'To Bill')")
    values = {}

    # Apply filters
    if filters:
        if filters.get("company"):
            po_conditions.append("po.company = %(company)s")
            values["company"] = filters["company"]
        if filters.get("from_date"):
            po_conditions.append("po.transaction_date >= %(from_date)s")
            values["from_date"] = filters["from_date"]
        if filters.get("to_date"):
            po_conditions.append("po.transaction_date <= %(to_date)s")
            values["to_date"] = filters["to_date"]

    po_where = " AND ".join(po_conditions)

    query = f"""
        SELECT
            po.name AS purchase_order,
            po.transaction_date,
            po.company,
            po.status AS po_status,
            CASE 
                WHEN COUNT(grn.name) > 0 THEN 'Yes' 
                ELSE 'No' 
            END AS grn_created,
            CASE 
                WHEN COUNT(grn.name) = 0 THEN 'No'
                WHEN COUNT(grn.name) = SUM(CASE WHEN grn.docstatus = 1 THEN 1 ELSE 0 END) THEN 'Yes'
                ELSE 'Partial'
            END AS grn_completed
        FROM `tabPurchase Order` po
        LEFT JOIN `tabGoods Receipt Note` grn 
               ON grn.purchase_order = po.name 
              AND grn.docstatus != 2  -- Exclude cancelled GRNs
        WHERE {po_where}
        GROUP BY po.name, po.transaction_date, po.company, po.status
        ORDER BY po.transaction_date DESC, po.name DESC
    """
    return frappe.db.sql(query, values=values, as_dict=1)

def _count_status_buckets(data):
    """Return counts for No GRN Created / Partial GRN / GRN Completed."""
    buckets = {
        "No GRN Created": 0,
        "Partial GRN": 0,
        "GRN Completed": 0,
    }
    for row in data or []:
        # Mutually exclusive mapping based on our computed fields
        if row.get("grn_created") == "No":
            buckets["No GRN Created"] += 1
        elif row.get("grn_completed") == "Partial":
            buckets["Partial GRN"] += 1
        elif row.get("grn_completed") == "Yes":
            buckets["GRN Completed"] += 1
    return buckets

def get_chart(data):
    """Frappe chart dict (pie) by GRN status."""
    b = _count_status_buckets(data)
    labels = [ _("No GRN Created"), _("Partial GRN"), _("GRN Completed") ]
    values = [ b["No GRN Created"], b["Partial GRN"], b["GRN Completed"] ]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"values": values}],
        },
        "type": "pie",
        "height": 250,
    }

def get_message_table(data):
    """Small HTML table (Status vs Count) shown above the grid."""
    b = _count_status_buckets(data)
    total = sum(b.values())
    # Basic, framework-safe HTML
    html = f"""
    <div>
      <h6 style="margin: 0 0 8px 0;">{_('Summary by GRN Status')}</h6>
      <table class="table table-bordered table-sm" style="max-width:420px;">
        <thead>
          <tr>
            <th>{_('Status')}</th>
            <th class="text-right">{_('Count')}</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>{_('No GRN Created')}</td><td class="text-right">{b['No GRN Created']}</td></tr>
          <tr><td>{_('Partial GRN')}</td><td class="text-right">{b['Partial GRN']}</td></tr>
          <tr><td>{_('GRN Completed')}</td><td class="text-right">{b['GRN Completed']}</td></tr>
          <tr>
            <td><strong>{_('Total')}</strong></td>
            <td class="text-right"><strong>{total}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>
    """
    return html

def get_summary(data):
    if not data:
        return []

    grn_not_created = 0
    grn_partial = 0
    grn_completed = 0

    for row in data:
        if row.grn_created == "No":
            grn_not_created += 1
        elif row.grn_completed == "Partial":
            grn_partial += 1
        elif row.grn_completed == "Yes":
            grn_completed += 1

    total = len(data)

    return [
        {"value": total,            "indicator": "blue",   "label": _("Total POs"),         "datatype": "Int"},
        {"value": grn_not_created,  "indicator": "red",    "label": _("No GRN Created"),    "datatype": "Int"},
        {"value": grn_partial,      "indicator": "orange", "label": _("Partial GRN"),       "datatype": "Int"},
        {"value": grn_completed,    "indicator": "green",  "label": _("GRN Completed"),     "datatype": "Int"},
    ]
