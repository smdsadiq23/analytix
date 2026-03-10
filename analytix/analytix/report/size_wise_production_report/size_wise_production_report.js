// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Size wise Production Report"] = {
    filters: [
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

        const isTotalRow = data.department === "TOTAL / AVERAGE";

        // ── Total row: bold everything ─────────────────────────────────────
        if (isTotalRow) {
            return `<span style="font-weight:700;">${value ?? ""}</span>`;
        }

        // ── Balance Qty: green if <= 0 (on/ahead of plan), red if > 0 (behind)
        // Balance = Planned Qty − Completed Qty, so positive means work still remaining
        if (column.fieldname === "balance_qty") {
            const num = parseInt(value);
            if (num === 0) return `<span style="color:#2e7d32; font-weight:500;">${value}</span>`;
            const color = num > 0 ? "#d32f2f" : "#2e7d32";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Completed %: red → orange → blue → green ──────────────────────
        if (column.fieldname === "completed_percent") {
            const num = parseFloat(String(value).replace("%", ""));
            let color = "#d32f2f";
            if (num >= 100)     color = "#2e7d32";
            else if (num >= 75) color = "#1565c0";
            else if (num >= 50) color = "#e65100";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        return html;
    },

    onload: function(report) {
        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Size sise Production Report" }
                ]
            });
        }
    }
};