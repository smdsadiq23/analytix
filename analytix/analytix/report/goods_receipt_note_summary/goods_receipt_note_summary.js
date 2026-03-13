// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Goods Receipt Note Summary"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Start Date"),
			fieldtype: "Date",
			default: moment().subtract(1, "months").startOf("month").format("YYYY-MM-DD"),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("End Date"),
			fieldtype: "Date",
			default: frappe.datetime.nowdate(),
			reqd: 1,
		},
	],

    onload(report) {
        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Goods Receipt Note Summary" },
                ],
            });
        }
    },	
};