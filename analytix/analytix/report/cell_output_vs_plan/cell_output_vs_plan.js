// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

// report: Cell Output vs Plan
// file: analytix/analytix/report/cell_output_vs_plan/cell_output_vs_plan.js

frappe.query_reports["Cell Output vs Plan"] = {
  "filters": [
    { fieldname: "date", label: "Date", fieldtype: "Date",
      default: frappe.datetime.get_today(), reqd: 1 },
    { fieldname: "physical_cell", label: "Physical Cell", fieldtype: "Data" }
  ]
};

