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

        const isTotalRow = data.buyer === "TOTAL / AVERAGE";

        // ── Total row: blank serial number, bold everything else ───────────
        if (isTotalRow) {
            if (column.fieldname === "row_num") return "";
            return `<span style="font-weight:700;">${value}</span>`;
        }

        // ── Yield %: green if ≤ 100% (on/under plan), red if > 100% ───────
        if (column.fieldname === "yield_pct") {
            const num   = parseFloat(String(value).replace("%", ""));
            const color = num > 100 ? "#2e7d32" : "#d32f2f";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Wastage/Excess: green if positive (saved), red if negative ─────
        if (column.fieldname === "wastage_excess") {
            const num = parseFloat(String(value).replace("%", ""));
            if (num === 0) return `<span style="color:#555;">${value}</span>`;
            const color = num > 0 ? "#2e7d32" : "#d32f2f";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Completed %: red → orange → blue → green ──────────────────────
        if (column.fieldname === "completed_pct") {
            const num = parseFloat(String(value).replace("%", ""));
            let color = "#d32f2f";
            if (num >= 100)      color = "#2e7d32";
            else if (num >= 75)  color = "#1565c0";
            else if (num >= 50)  color = "#e65100";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Balance Qty: red if negative (behind plan) ────────────────────
        if (column.fieldname === "balance_qty") {
            if (value < 0) return `<span style="color:#d32f2f; font-weight:500;">${value}</span>`;
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