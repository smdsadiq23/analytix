// Copyright (c) 2025, Cognitonx Logic India Private limited and contributors
// For license information, please see license.txt

frappe.query_reports["Cutting Completion Report"] = {
    hasRole(role) {
        if (frappe.user?.has_role) return frappe.user.has_role(role);
        const roles =
            frappe.boot?.user_info?.[frappe.session.user]?.roles || frappe.user_roles || [];
        return Array.isArray(roles) && roles.includes(role);
    },

    get_datatable_options(options) {
        options.showTotalRow = true;
        return options;
    },

    formatter(value, row, column, data, default_formatter) {
        const safeValueForDefault = (value == null || value === "") ? "" : String(value);
        let html = default_formatter(safeValueForDefault, row, column, data, default_formatter);

        const fieldname = (column.fieldname || "").toLowerCase();

        const fmt = (n, p = 2) => {
            const num = Number(n || 0);
            if (!isFinite(num)) return "";
            return num.toFixed(p);
        };

        // ✅ TOTAL ROW
        const isTotalRow = !row && !data;
        if (isTotalRow) {
            if (fieldname === "ocn") {
                return `<b>${__("Total")}</b>`;
            }
            if (fieldname === "file_consumption" || fieldname === "actual_consumption") {
                return `<b></b>`;
            }
            return `<b>${html}</b>`;
        }

        if (!data) return html;

        const isStatus = fieldname === "status";
        const isApproval = fieldname === "approval";
        const isCutPct = fieldname === "cut_completion_pct";

        const rowStatus = data.status || "";

        const wrapWithStatusBg = (content) => {
            let bg = "";
            if (rowStatus === "Inprogress") {
                bg = "#fff9c4"; // light yellow
            } else if (rowStatus === "Completed") {
                bg = "#c8e6c9"; // light green
            } else if (rowStatus === "Verified") {
                bg = "#bbdefb"; // light blue
            }
            if (!bg) return content;
            return `<span class="cut-status-bg" style="display:block;background-color:${bg};">${content}</span>`;
        };

        // Cut Completion %
        if (isCutPct) {
            const pct = Number(data.cut_completion_pct || 0);
            const pctHtml = `<span>${fmt(pct, 2)}%</span>`;
            return wrapWithStatusBg(pctHtml);
        }

        // ✅ Editable Status Dropdown
        if (isStatus) {
            const docname = data.ocn;
            const currentValue = rowStatus;
            const currentApproval = data.approval || "";
            const isVerifier = this.hasRole("CCR Verifier");

            const canEditStatus = isVerifier && docname && currentApproval !== "Approved";

            if (canEditStatus) {
                const options = ["Yet to Start", "Inprogress", "Completed", "Verified"].map(opt => {
                    const selected = opt === currentValue ? "selected" : "";
                    return `<option value="${opt}" ${selected}>${opt}</option>`;
                }).join("");

                const selectHtml = `
                    <div data-ocn="${docname}">
                        <select class="report-status-select"
                                data-docname="${docname}"
                                data-doctype="Sales Order"
                                data-fieldname="custom_consumption_status"
                                style="width:100%; padding:4px; border-radius:4px;">
                            ${options}
                        </select>
                    </div>
                `;
                return wrapWithStatusBg(selectHtml);
            } else {
                const statusHtml = `<span>${frappe.utils.escape_html(currentValue)}</span>`;
                return wrapWithStatusBg(statusHtml);
            }
        }

        // ✅ Approval Column - Enhanced Display
        if (isApproval) {
            const docname = data.ocn;
            if (!docname) return wrapWithStatusBg(html);

            const currentApproval = data.approval || "";
            const rowStatus = data.status || "";
            const withReplenishment = Number(data.with_replenishment || 0);
            const isFactoryManager = this.hasRole("Factory Manager");

            // 🔹 Display logic
            let displayText = currentApproval;

            if (rowStatus === "Verified" && !currentApproval) {
                displayText = "Yet to Confirm";
            } else if (currentApproval === "Approved") {
                displayText = withReplenishment ? "App with Replenishment" : "Approved";
            }

            // 🔹 Editability logic
            const canApprove = (
                !currentApproval && 
                rowStatus === "Verified" && 
                isFactoryManager
            );

            if (canApprove) {
                const selectHtml = `
                    <div data-ocn="${docname}">
                        <select class="report-status-select"
                                data-docname="${docname}"
                                data-doctype="Sales Order"
                                data-fieldname="custom_approval"
                                style="width:100%; padding:4px; border-radius:4px;">
                            <option value="">Yet to Confirm</option>
                            <option value="Approved">Approved</option>
                        </select>
                    </div>
                `;
                return wrapWithStatusBg(selectHtml);
            } else {
                const spanHtml = `<span data-ocn="${docname}">${frappe.utils.escape_html(displayText)}</span>`;
                return wrapWithStatusBg(spanHtml);
            }
        }

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

            if (newValue === oldValue) return;

            // ✅ Handle Status Update
            if (fieldname === "custom_consumption_status") {
                if (!this.hasRole("CCR Verifier")) {
                    frappe.msgprint(__("You do not have permission to update cutting status."));
                    $el.val(oldValue);
                    return;
                }

                const allRows = report.data || [];
                const row = allRows.find(r => r.ocn === docname);
                if (!row) {
                    frappe.msgprint(__("Row data not found."));
                    $el.val(oldValue);
                    return;
                }

                if (row.approval === "Approved") {
                    frappe.msgprint(__("Status cannot be changed after approval."));
                    $el.val(oldValue);
                    return;
                }

                $el.css("opacity", 0.6);
                frappe.call({
                    method: "frappe.client.set_value",
                    args: { doctype, name: docname, fieldname, value: newValue },
                    callback: (r) => {
                        if (r.exc) {
                            frappe.msgprint(__("Failed to update status."));
                            $el.val(oldValue);
                            return;
                        }
                        frappe.show_alert({ message: __("Status updated"), indicator: "green" });
                        $el.data("old-value", newValue);
                        (report.data || []).forEach(rw => {
                            if (rw.ocn === docname) {
                                rw.status = newValue;
                            }
                        });
                    },
                    always: () => {
                        $el.css("opacity", 1);
                    }
                });
                return;
            }

            // ✅ Handle Factory Manager Approval (3 separate set_value calls)
            if (fieldname === "custom_approval") {
                if (!this.hasRole("Factory Manager")) {
                    frappe.msgprint(__("Only Factory Managers can approve."));
                    $el.val(oldValue);
                    return;
                }

                const allRows = report.data || [];
                const row = allRows.find(r => r.ocn === docname);
                if (!row) {
                    frappe.msgprint(__("Row not found."));
                    $el.val(oldValue);
                    return;
                }

                if (row.status !== "Verified") {
                    frappe.msgprint(__("Only 'Verified' status can be approved."));
                    $el.val(oldValue);
                    return;
                }

                if (newValue !== "Approved") {
                    $el.val(oldValue);
                    return;
                }

                $el.css("opacity", 0.6);

                // 1. Update approval status
                frappe.call({
                    method: "frappe.client.set_value",
                    args: {
                        doctype: "Sales Order",
                        name: docname,
                        fieldname: "custom_approval",
                        value: "Approved"
                    },
                    callback: (r1) => {
                        if (r1.exc) {
                            console.error("Approval update failed:", r1.exc);
                            frappe.msgprint(__("Failed to update approval."));
                            $el.val(oldValue);
                            $el.css("opacity", 1);
                            return;
                        }

                        // 2. Update approved_by
                        frappe.call({
                            method: "frappe.client.set_value",
                            args: {
                                doctype: "Sales Order",
                                name: docname,
                                fieldname: "custom_approved_by",
                                value: frappe.session.user
                            },
                            callback: (r2) => {
                                if (r2.exc) {
                                    console.error("Approved By update failed:", r2.exc);
                                }

                                // 3. Update approved_on
                                frappe.call({
                                    method: "frappe.client.set_value",
                                    args: {
                                        doctype: "Sales Order",
                                        name: docname,
                                        fieldname: "custom_approved_on",
                                        value: frappe.datetime.now_datetime()
                                    },
                                    callback: (r3) => {
                                        if (r3.exc) {
                                            console.error("Approved On update failed:", r3.exc);
                                        }

                                        frappe.show_alert({ message: __("Approved"), indicator: "green" });
                                        $el.data("old-value", "Approved");

                                        // Update report data
                                        (report.data || []).forEach(rw => {
                                            if (rw.ocn === docname) {
                                                rw.approval = "Approved";
                                                rw.custom_approved_by = frappe.session.user;
                                                rw.custom_approved_on = frappe.datetime.now_datetime();
                                            }
                                        });

                                        // Replace dropdown with plain text
                                        const $cell = $el.closest("td");
                                        $cell.html(`<span>Approved</span>`);
                                        $el.css("opacity", 1);
                                    },
                                    always: () => {
                                        // Ensure opacity reset even if call fails
                                        if (!r3 || r3.exc) $el.css("opacity", 1);
                                    }
                                });
                            },
                            always: () => {
                                // Proceed to approved_on even if approved_by fails (unlikely)
                            }
                        });
                    }
                });
                return;
            }

            // Handle other editable fields
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