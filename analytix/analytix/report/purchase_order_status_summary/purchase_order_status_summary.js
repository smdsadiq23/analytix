// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Order Status Summary"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company")
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        }
    ],

    onload(report) {
        CX.mountBreadcrumb({
        wrapper: report.page.wrapper || report.page.$wrapper,
        trail: [
            { label: "KPI Hub", href: "/app/kpi-hub" },
            { label: "Purchase Order Status Summary" }
        ]
        });
    }  
};
