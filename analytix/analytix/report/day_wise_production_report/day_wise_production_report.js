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

    formatter(value, row, column, data, default_formatter) {
        let html = default_formatter(value, row, column, data);
        if (!data || value === null || value === undefined) return html;

        // ── Balance Qty: green if >= 0, red if negative
        if (column.fieldname === "balance_qty") {
            const num = parseInt(value);
            const color = num >= 0 ? "#2e7d32" : "#d32f2f";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Completed %: green if >= 100%, red if < 100%
        // value arrives as "85.0%" string from Python — strip % before comparing
        if (column.fieldname === "completed_percent") {
            const num = parseFloat(String(value).replace("%", ""));
            const color = num >= 100 ? "#2e7d32" : "#d32f2f";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        return html;
    },

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