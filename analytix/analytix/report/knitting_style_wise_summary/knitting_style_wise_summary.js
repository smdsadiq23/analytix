// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Knitting Style wise Summary"] = {
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

        const isTotalRow = data.style === "TOTAL / AVERAGE";

        // ── Bold + background for totals row ──────────────────────────────
        if (isTotalRow) {
            return `<span style="font-weight:700;">${value}</span>`;
        }

        // ── Yield %: green if ≤ 100% (on/under plan), red if > 100% ──────
        if (column.fieldname === "yield_pct") {
            const num   = parseFloat(String(value).replace("%", ""));
            const color = num > 100 ? "#2e7d32" : "#d32f2f";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Variance: green if > 0 (saved yarn), red if < 0 (over-used) ──
        if (column.fieldname === "variance") {
            if (value === 0) return `<span style="color:#555;">${value}</span>`;
            const color = value > 0 ? "#2e7d32" : "#d32f2f";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Completed %: red → amber → green gradient ──────────────────
        if (column.fieldname === "completed_pct") {
            const num = parseFloat(String(value).replace("%", ""));
            let color = "#d32f2f";        // < 50%  red
            if (num >= 100) color = "#2e7d32";   // done  green
            else if (num >= 75) color = "#1565c0"; // near  blue
            else if (num >= 50) color = "#e65100"; // half  orange
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
                    { label: "Knitting Style Wise Summary" },
                ],
            });
        }
    },
};