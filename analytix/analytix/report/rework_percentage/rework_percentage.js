// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Rework Percentage"] = {
	"filters": [
		{ fieldname: "from_date", label: "From Date", fieldtype: "Date", 
		default: frappe.datetime.add_days(frappe.datetime.get_today(), -1), reqd: 1 },
		{ fieldname: "to_date", label: "To Date", fieldtype: "Date",
		default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "physical_cell", label: "Physical Cell", fieldtype: "Data" },
		{ fieldname: "operation", label: "Operation", fieldtype: "Data" }
	]
};