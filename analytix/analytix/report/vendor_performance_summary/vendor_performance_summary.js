// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Vendor Performance Summary"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date (Sent)"),
			fieldtype: "Date",
			default: moment().subtract(1, "months").startOf("month").format("YYYY-MM-DD"),
		},
		{
			fieldname: "to_date",
			label: __("To Date (Sent)"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "supplier",
			label: __("Vendor"),
			fieldtype: "Link",
			options: "Supplier",
		},
	],

    onload(report) {
        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Vendor Performance Summary" },
                ],
            });
        }
    },	
};
