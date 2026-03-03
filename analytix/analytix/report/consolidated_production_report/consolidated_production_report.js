// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Consolidated Production Report"] = {
	filters: [
		{
			fieldname: "as_on_date",
			label: __("As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
	],

	onload(report) {
		CX.mountBreadcrumb({
			wrapper: report.page.wrapper || report.page.$wrapper,
			trail: [{ label: "KPI Hub", href: "/app/kpi-hub" }, { label: "Consolidated Production Report" }],
		});
	},
};
