// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Fabric Pending Inhouse"] = {

    // // ------------------------------------------------------------------
    // // Filter definitions
    // // ------------------------------------------------------------------
    // filters: [
    //     {
    //         fieldname: "from_date",
    //         label:     __("From Date"),
    //         fieldtype: "Date",
    //         default:   frappe.datetime.add_months(frappe.datetime.get_today(), -1),
    //     },
    //     {
    //         fieldname: "to_date",
    //         label:     __("To Date"),
    //         fieldtype: "Date",
    //         default:   frappe.datetime.get_today(),
    //     },
    //     {
    //         fieldname: "customer",
    //         label:     __("Buyer"),
    //         fieldtype: "Link",
    //         options:   "Customer",
    //     },
    //     {
    //         fieldname: "responsible",
    //         label:     __("Responsible"),
    //         fieldtype: "Select",
    //         options:   "\nFabric\nMerchant\nProduction\nOther",
    //     },
    // ],

    onload(report) {
        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Fabric Pending Inhouse" },
                ],
            });
        }
    },		

    // ------------------------------------------------------------------
    // Column formatters — render Remarks & Manager Remarks as <select>
    // The selected value is persisted via the save_remark API call.
    // ------------------------------------------------------------------
    formatter(value, row, column, data, default_formatter) {

        if (column.fieldname === "remarks") {
            return _make_select(data, "remarks", value, [
                { value: "",            label: "—" },
                { value: "Short Close", label: "Short Close" },
            ]);
        }

        if (column.fieldname === "manager_remarks") {
            return _make_select(data, "manager_remarks", value, [
                { value: "",         label: "—" },
                { value: "Approved", label: "Approved" },
            ]);
        }

        // Highlight negative balance in orange
        if (column.fieldname === "balance_to_receive" && value < 0) {
            return `<span style="color:#d97706;font-weight:600;">${flt(value, 2)}</span>`;
        }

        return default_formatter(value, row, column, data);
    },

    // ------------------------------------------------------------------
    // After report render — attach change listeners to every <select>
    // ------------------------------------------------------------------
    after_datatable_render(datatable) {
        _attach_listeners(datatable);
    },

    // Re-attach after pagination / sort / refresh
    onload(report) {
        report.page.wrapper.on("report-rendered", () => {
            _attach_listeners();
        });
    },
};

// ------------------------------------------------------------------
// Helpers (module-private)
// ------------------------------------------------------------------

/**
 * Build an HTML <select> element for a report cell.
 */
function _make_select(data, field, current_value, options) {
    if (!data) return current_value || "";

    const ocn    = data.ocn    || "";
    const colour = data.colour || "";

    let html = `<select
        class="fpih-remark-select"
        data-ocn="${frappe.utils.escape_html(ocn)}"
        data-colour="${frappe.utils.escape_html(colour)}"
        data-field="${field}"
        style="width:100%;border:none;background:transparent;font-size:var(--text-sm);"
    >`;

    options.forEach(opt => {
        const selected = (opt.value === (current_value || "")) ? "selected" : "";
        html += `<option value="${opt.value}" ${selected}>${opt.label}</option>`;
    });

    html += `</select>`;
    return html;
}

/**
 * Attach onChange listeners to all remark selects in the rendered table.
 * Calls the whitelisted Python method to persist the value.
 */
function _attach_listeners(datatable) {
    const $root = datatable
        ? $(datatable.wrapper)
        : $(".dt-scrollable");   // fallback selector

    $root.find(".fpih-remark-select").off("change.fpih").on("change.fpih", function () {
        const $sel           = $(this);
        const ocn            = $sel.data("ocn");
        const colour         = $sel.data("colour");
        const field          = $sel.data("field");
        const value          = $sel.val();
        const $originalColor = $sel.css("color");

        // Optimistic UI feedback
        $sel.css("color", "#6366f1");

        frappe.call({
            method: "analytix.analytix.report.fabric_pending_inhouse.fabric_pending_inhouse.save_remark",
            // ↑ Replace the dotted path with the actual app/module path
            args: { ocn, colour, field, value },
            callback(r) {
                if (!r.exc) {
                    $sel.css("color", "#16a34a");   // green = saved
                    setTimeout(() => $sel.css("color", $originalColor), 1500);

                    // If both selects in this row now have values,
                    // a full report refresh will move the row to the bottom.
                    const $row      = $sel.closest("tr");
                    const $siblings = $row.find(".fpih-remark-select");

                    if ($siblings.length === 2) {
                        const allFilled = [...$siblings].every(s => $(s).val() !== "");
                        if (allFilled) {
                            frappe.query_report.refresh();
                        }
                    }
                } else {
                    $sel.css("color", "#dc2626");   // red = error
                    frappe.show_alert({ message: __("Failed to save remark"), indicator: "red" });
                }
            },
        });
    });
}