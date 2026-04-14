# Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt
#
# Owner Dashboard backend
# Re-exports get_dashboard_data from shopfloor_performance so the owner
# dashboard page can call it directly without duplicating any SQL.

import frappe
from analytix.analytix.page.shopfloor_performance.shopfloor_performance import (
    get_dashboard_data as _get_dashboard_data,
)


@frappe.whitelist()
def get_dashboard_data(date=None):
    """
    Proxy to shopfloor_performance.get_dashboard_data.
    Returns the same structured list of style rows used by the shopfloor
    card grid; the owner_dashboard.js aggregates these into chart series.
    """
    return _get_dashboard_data(date=date)
