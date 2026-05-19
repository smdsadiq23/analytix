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

    // ── Formatter ────────────────────────────────────────────────────────────
    // Kept lean: avoid per-cell string parsing where the value is already a
    // number (Frappe passes the raw value for Int columns, not a string).
    formatter(value, row, column, data, default_formatter) {
        if (!data || value === null || value === undefined) {
            return default_formatter(value, row, column, data);
        }

        // Total/average summary row — bold everything
        if (data.department === "TOTAL / AVERAGE") {
            return `<span style="font-weight:700">${value ?? ""}</span>`;
        }

        const fn = column.fieldname;

        // Balance Qty — Int column, value is already numeric
        if (fn === "balance_qty") {
            const num = Number(value);
            if (num === 0) return `<span style="color:#2e7d32;font-weight:500">${value}</span>`;
            const color = num > 0 ? "#d32f2f" : "#2e7d32";
            return `<span style="color:${color};font-weight:500">${value}</span>`;
        }

        // Completed % — stored as "75.0%" string; parse once
        if (fn === "completed_percent") {
            const num = parseFloat(value);   // "75.0%" → 75
            let color = "#d32f2f";
            if      (num >= 100) color = "#2e7d32";
            else if (num >= 75)  color = "#1565c0";
            else if (num >= 50)  color = "#e65100";
            return `<span style="color:${color};font-weight:500">${value}</span>`;
        }

        return default_formatter(value, row, column, data);
    },

    // ── Lifecycle ────────────────────────────────────────────────────────────
    onload(report) {
        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Size wise Production Report" }
                ]
            });
        }
    }
};