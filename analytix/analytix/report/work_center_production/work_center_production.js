// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt


frappe.query_reports["Work Center Production"] = {
	filters: [
		{
			fieldname: "as_on_date",
			label: __("Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "unit",
			label: __("Unit"),
			fieldtype: "Link",
			options: "Factory Business Unit",
			get_query: () => {
				return {
					filters: { name: ["!=", ""] }
				};
			}
		},
		{
			fieldname: "ocn",
			label: __("OCN (Sales Order)"),
			fieldtype: "Link",
			options: "Sales Order",
			get_query: () => {
				return {
					filters: { docstatus: 1 }
				};
			},
			reqd: 1
		}
	],

	onload(report) {
		if (window.CX && CX.mountBreadcrumb) {
			CX.mountBreadcrumb({
				wrapper: report.page.wrapper || report.page.$wrapper,
				trail: [
					{ label: "KPI Hub", href: "/app/kpi-hub" },
					{ label: "Work Center Production" }
				],
			});
		}
	},
};