// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Knitting Production Report"] = {
    filters: [
        {
            fieldname: "date",
            label: __("Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: "buyer",
            label: __("Buyer"),
            fieldtype: "Link",
            options: "Customer",
        },
        {
            fieldname: "style",
            label: __("Style"),
            fieldtype: "Data",
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        let html = default_formatter(value, row, column, data);
        if (!data || value === null || value === undefined) return html;

        // ── Yield %: red if > 100% (over-consumed), green if <= 100% (on/under plan)
        if (column.fieldname === "yield_pct") {
            const num   = parseFloat(String(value).replace("%", ""));
            const color = num > 100 ? "#2e7d32" : "#d32f2f";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Wastage/Excess %: red if positive (over-used), green if negative (saved)
        if (column.fieldname === "wastage_excess") {
            const num = parseFloat(String(value).replace("%", ""));
            if (num === 0) return `<span style="color:#555;">${value}</span>`;
            const color = num > 0 ? "#2e7d32" : "#d32f2f";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        return html;
    },

    onload(report) {
        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Knitting Production Report" },
                ],
            });
        }
    },
};