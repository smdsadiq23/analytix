# Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document


class OrderStyleTracker(Document):
	pass


def validate(self):
    if frappe.db.exists("Order Style Tracker", {
        "sales_order": self.sales_order,
        "style": self.style,
        "name": ("!=", self.name)
    }):
        frappe.throw(_("Record already exists for {0} - {1}").format(self.sales_order, self.style))