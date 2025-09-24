// Copyright (c) 2025, CognitionX Logic India Private Limited
// For license information, please see license.txt


frappe.query_reports["Flow Rate"] = {
filters: [
{ fieldname: "date", label: "Date", fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
{ fieldname: "physical_cell", label: "Physical Cell", fieldtype: "Data" },
{ fieldname: "operation", label: "Operation", fieldtype: "Link", options: "Operation" }
]
};