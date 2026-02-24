// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Day Wise Production Report"] = {
    filters: [
        {
            fieldname: "date",
            label: __("Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        },
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Physical Cell"
        },
        {
            fieldname: "buyer",
            label: __("Buyer"),
            fieldtype: "Link",
            options: "Customer"
        },
        {
            fieldname: "style",
            label: __("Style"),
            fieldtype: "Data"
        }
    ],

    onload: function(report) {
        if (typeof CX !== 'undefined' && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Day Wise Production Report" }
                ]
            });
        }
        console.log("Day Wise Production Report loaded");
    }
};