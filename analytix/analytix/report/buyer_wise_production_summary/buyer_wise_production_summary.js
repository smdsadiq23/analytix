// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Buyer wise Production Summary"] = {
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
        if (!data) return html;

        const isTotalRow = data.buyer === "TOTAL / AVERAGE";

        // ── Total row: blank serial, bold everything else ──────────────────
        if (isTotalRow) {
            if (column.fieldname === "row_num") return "";
            if (value === null || value === undefined || value === "") return "";
            return `<span style="font-weight:700;">${value}</span>`;
        }

        if (value === null || value === undefined) return html;

        // ── Balance Qty: positive = work remaining (red), <= 0 = done (green)
        if (column.fieldname === "balance_qty") {
            if (value === 0) return `<span style="color:#2e7d32; font-weight:500;">${value}</span>`;
            const color = value > 0 ? "#d32f2f" : "#2e7d32";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        // ── Completed %: red -> orange -> blue -> green ────────────────────
        if (column.fieldname === "completed_pct") {
            const num = parseFloat(String(value).replace("%", ""));
            let color = "#d32f2f";
            if (num >= 100)      color = "#2e7d32";
            else if (num >= 75)  color = "#1565c0";
            else if (num >= 50)  color = "#e65100";
            return `<span style="color:${color}; font-weight:500;">${value}</span>`;
        }

        return html;
    },

    onload(report) {
        attachFilterClearButtons(report);

        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Buyer wise Production Summary" },
                ],
            });
        }
    },
};

function attachFilterClearButtons(report) {
    setTimeout(() => {
        const fields = report.page.fields_dict;
        if (!fields) return;
        Object.values(fields).forEach(field => {
            if (!field || !field.$wrapper) return;
            const $input = field.$wrapper.find("input");
            if (!$input.length) return;
            if (!$input.parent().hasClass("filter-input-wrap")) {
                $input.wrap('<div class="filter-input-wrap" style="position:relative; display:inline-block; width:100%;"></div>');
            }
            const $clear = $('<span title="Clear">&#x2715;</span>').css({
                position: "absolute", right: "8px", top: "50%", transform: "translateY(-50%)",
                cursor: "pointer", color: "#aaa", fontSize: "13px", lineHeight: "1", display: "none", zIndex: 10,
            }).hover(function() { $(this).css("color", "#555"); }, function() { $(this).css("color", "#aaa"); });
            $input.parent().append($clear);
            $input.css("paddingRight", "24px");
            const toggle = () => $clear.toggle(!!$input.val());
            $input.on("input change", toggle);
            toggle();
            $clear.on("click", () => { field.set_value(""); field.value = ""; $clear.hide(); report.refresh(); });
        });
    }, 300);
}