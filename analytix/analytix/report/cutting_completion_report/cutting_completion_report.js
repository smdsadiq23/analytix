// Copyright (c) 2025, Cognitonx Logic India Private limited and contributors
// For license information, please see license.txt

frappe.query_reports["Cutting Completion Report"] = {
    hasRole(role) {
        if (frappe.user?.has_role) return frappe.user.has_role(role);
        const roles =
            frappe.boot?.user_info?.[frappe.session.user]?.roles || frappe.user_roles || [];
        return Array.isArray(roles) && roles.includes(role);
    },

    // Helper to compute status from quantities
    getRowStatus(data) {
        const cutQtyActual = Number(data.cut_qty_actual || 0);
        const orderQty = Number(data.order_qty || 0);

        if (orderQty > 0) {
            const percent = (cutQtyActual / orderQty) * 100;
            if (percent >= 98) {
                return "Completed";
            }
        }
        return "Inprogress";
    },

    // Ensure total row shows even if "Add Total Row" isn't applied in DB yet
    get_datatable_options(options) {
        options.showTotalRow = true;
        return options;
    },

    formatter(value, row, column, data, default_formatter) {
        const safeValueForDefault = (value == null || value === "") ? "" : String(value);
        let html = default_formatter(safeValueForDefault, row, column, data, default_formatter);

        const fieldname = (column.fieldname || "").toLowerCase();

        // Version-safe number formatting (no frappe.format_number dependency)
        const fmt = (n, p = 2) => {
            const num = Number(n || 0);
            if (!isFinite(num)) return "";
            return num.toFixed(p);
        };

        // ✅ TOTAL ROW handling (must run before touching `data`)
        // In many Frappe versions, total row comes with row = null and data = null
        const isTotalRow = !row && !data;
        if (isTotalRow) {
            const rows = (frappe.query_report?.data || []).filter(r => r && typeof r === "object");

            const avgOf = (fname) => {
                const nums = rows
                    .map(r => Number(r?.[fname]))
                    .filter(v => !isNaN(v));
                return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : 0;
            };

            // Overall Cut Completion % at totals row = SUM(cut_qty_actual)/SUM(order_qty)*100
            const overallCutPct = () => {
                const sumCut = rows.reduce((s, r) => s + (Number(r?.cut_qty_actual) || 0), 0);
                const sumOrder = rows.reduce((s, r) => s + (Number(r?.order_qty) || 0), 0);
                return sumOrder ? (sumCut / sumOrder) * 100 : 0;
            };

            if (fieldname === "ocn") {
                return `<b>${__("Totals / Avg")}</b>`;
            }
            if (fieldname === "file_consumption") {
                return `<b>${fmt(avgOf("file_consumption"), 2)}</b>`;
            }
            if (fieldname === "actual_consumption") {
                return `<b>${fmt(avgOf("actual_consumption"), 2)}</b>`;
            }
            if (fieldname === "cut_completion_pct") {
                return `<b>${fmt(overallCutPct(), 2)}%</b>`;
            }

            // Default: keep frappe's computed total value (usually SUM) for other columns
            return `<b>${html}</b>`;
        }

        // ✅ For non-data rows, keep default
        if (!data) return html;

        const isStatus = fieldname === "status";
        const isFolding = fieldname === "folding";
        const isApproval = fieldname === "approval";
        const isCutPct = fieldname === "cut_completion_pct";

        const rowStatus = this.getRowStatus(data);

        // Helper to wrap a cell with background color based on status
        const wrapWithStatusBg = (content) => {
            let bg = "";
            if (rowStatus === "Inprogress") {
                bg = "#fff9c4"; // light yellow
            } else if (rowStatus === "Completed") {
                bg = "#c8e6c9"; // light green
            }
            if (!bg) return content;
            return `<span class="cut-status-bg" style="display:block;background-color:${bg};">${content}</span>`;
        };

        // Cut Completion % (normal rows)
        if (isCutPct) {
            const pct = Number(data.cut_completion_pct || 0);
            const pctHtml = `<span>${fmt(pct, 2)}%</span>`;
            return wrapWithStatusBg(pctHtml);
        }

        // Folding (editable textarea)
        if (isFolding) {
            const docname = data.can_cut_name;
            if (!docname) return wrapWithStatusBg(html);

            const safeValue = frappe.utils.escape_html(value || "");
            const customHtml = `
                <textarea class="report-editable-field"
                        data-docname="${docname}"
                        data-doctype="Can Cut"
                        data-fieldname="folding"
                        rows="1"
                        style="width:100%; padding:4px; resize:vertical;">${safeValue}</textarea>
            `;
            return wrapWithStatusBg(customHtml);
        }

        // Status – read-only, derived from quantities
        if (isStatus) {
            const statusText = rowStatus;
            const statusHtml = `<span>${frappe.utils.escape_html(statusText)}</span>`;
            return wrapWithStatusBg(statusHtml);
        }

        // Approval column
        if (isApproval) {
            const docname = data.ocn;  // Sales Order
            if (!docname) return wrapWithStatusBg(html);

            const currentValue = value || data.approval || "";
            const isApprover = this.hasRole("Cut Completion Approver");

            // Once Approved, always render as plain text (no dropdown) for everyone
            if (currentValue === "Approved") {
                const spanHtml = `<span data-ocn="${docname}">${frappe.utils.escape_html(currentValue)}</span>`;
                return wrapWithStatusBg(spanHtml);
            }

            const canEdit =
                data.is_first_row &&
                isApprover &&
                rowStatus === "Completed";

            // If user can edit (approver + status Completed + first row) show dropdown
            if (canEdit) {
                const selectedApproved = currentValue === "Approved" ? "selected" : "";
                const selectHtml = `
                    <div data-ocn="${docname}">
                        <select class="report-status-select"
                                data-docname="${docname}"
                                data-doctype="Sales Order"
                                data-fieldname="custom_cut_approval_status"
                                style="width:100%; padding:4px; border-radius:4px;">
                            <option value=""></option>
                            <option value="Approved" ${selectedApproved}>Approved</option>
                        </select>
                    </div>
                `;
                return wrapWithStatusBg(selectHtml);
            }

            // Otherwise, show plain text (no editing)
            const spanHtml = `<span data-ocn="${docname}">${frappe.utils.escape_html(currentValue || "")}</span>`;
            return wrapWithStatusBg(spanHtml);
        }

        // Default: just apply background to whatever default formatter returned
        return wrapWithStatusBg(html);
    },

    onload(report) {
        CX.mountBreadcrumb({
            wrapper: report.page.wrapper || report.page.$wrapper,
            trail: [
                { label: "KPI Hub", href: "/app/kpi-hub" },
                { label: "Cutting Completion Report" }
            ]
        });

        const $wrap = report.page.wrapper;

        const save = frappe.utils.debounce(function (e) {
            const $el = $(e.currentTarget);
            const docname = $el.data("docname");
            const doctype = $el.data("doctype");
            const fieldname = $el.data("fieldname");
            const newValue = $el.val();
            const oldValue = $el.data("old-value");

            // Prevent unnecessary save if no change
            if (newValue === oldValue) return;

            // Approval field: only 2 validations
            // 1. User has Cut Completion Approver role
            // 2. Status is Completed (for that row / OCN)
            if (fieldname === "custom_cut_approval_status") {
                if (!this.hasRole("Cut Completion Approver")) {
                    frappe.msgprint(__("You are not allowed to approve cutting completion."));
                    $el.val(oldValue);
                    return;
                }

                // Find the row for this OCN (first row preferred)
                const allRows = report.data || [];
                const row =
                    allRows.find(r => r.ocn === docname && r.is_first_row) ||
                    allRows.find(r => r.ocn === docname);

                if (!row) {
                    frappe.msgprint(__("Unable to find row data for this Sales Order."));
                    $el.val(oldValue);
                    return;
                }

                const rowStatus = this.getRowStatus(row);
                if (rowStatus !== "Completed") {
                    frappe.msgprint(__("Approval is only allowed when Status is Completed."));
                    $el.val(oldValue);
                    return;
                }

                // Proceed to save without any other validation
                $el.css("opacity", 0.6);
                frappe.call({
                    method: "frappe.client.set_value",
                    args: {
                        doctype,
                        name: docname,
                        fieldname,
                        value: newValue
                    },
                    callback: (r) => {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __("Approval updated"),
                                indicator: "green"
                            });
                            $el.data("old-value", newValue);

                            // Update report.data so UI stays in sync
                            (report.data || []).forEach(rw => {
                                if (rw.ocn === docname) {
                                    rw.approval = newValue;
                                }
                            });

                            // If approved, immediately turn dropdown into plain text
                            if (newValue === "Approved") {
                                const $cell = $el.closest("td");
                                $cell.html(
                                    `<span data-ocn="${docname}">${frappe.utils.escape_html(newValue)}</span>`
                                );
                            }
                        } else {
                            $el.val(oldValue);
                        }
                    },
                    always: () => {
                        $el.css("opacity", 1);
                    }
                });

                return;
            }

            // Handle other editable fields (e.g., folding)
            $el.css("opacity", 0.6);
            frappe.call({
                method: "frappe.client.set_value",
                args: { doctype, name: docname, fieldname, value: newValue },
                callback(r) {
                    if (!r.exc) {
                        frappe.show_alert({ message: __("Saved"), indicator: "green" });
                        $el.data("old-value", newValue);
                    } else {
                        frappe.msgprint(__("Save failed"));
                        $el.val(oldValue);
                    }
                },
                always() {
                    $el.css("opacity", 1);
                }
            });
        }.bind(this), 600);

        // Track original value on focus
        $wrap.on("focus", ".report-editable-field, .report-status-select", function () {
            $(this).data("old-value", $(this).val());
        });

        $wrap.on("blur", ".report-editable-field", save);
        $wrap.on("change", ".report-status-select", save);
    }
};
