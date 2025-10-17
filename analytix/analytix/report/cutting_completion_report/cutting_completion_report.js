// Copyright (c) 2025, Cognitonx Logic India Private limited and contributors
// For license information, please see license.txt

frappe.query_reports["Cutting Completion Report"] = {
    hasRole(role) {
        if (frappe.user?.has_role) return frappe.user.has_role(role);
        const roles =
            frappe.boot?.user_info?.[frappe.session.user]?.roles || frappe.user_roles || [];
        return Array.isArray(roles) && roles.includes(role);
    },

    formatter(value, row, column, data, default_formatter) {
        const safeValueForDefault = (value == null || value === '') ? '' : String(value);
        const html = default_formatter(safeValueForDefault, row, column, data, default_formatter);
        if (!data) return html;

        const fieldname = (column.fieldname || "").toLowerCase();
        const isStatus = fieldname === "status";
        const isFolding = fieldname === "folding";

        // Handle Folding (unchanged)
        if (isFolding) {
            const docname = data.can_cut_name;
            if (!docname) return html;

            const safeValue = frappe.utils.escape_html(value || "");
            return `
                <textarea class="report-editable-field"
                        data-docname="${docname}"
                        data-doctype="Can Cut"
                        data-fieldname="folding"
                        rows="1"
                        style="width:100%; padding:4px; resize:vertical;">${safeValue}</textarea>
            `;
        }

        // Handle Status Dropdown with workflow
        if (isStatus) {
            const docname = data.ocn;
            const currentValue = value || "Prepared";
            const isFactoryManager = this.hasRole("Factory Manager");

            // Base status flow
            const statusOrder = ["Prepared", "Verified", "Pending for Approval", "Approved"];
            
            // Filter out "Approved" if user is not Factory Manager
            let allowedStatuses = isFactoryManager 
                ? [...statusOrder] 
                : statusOrder.filter(s => s !== "Approved");

            if (data.is_first_row) {
                const options = allowedStatuses.map(opt =>
                    `<option value="${opt}" ${opt === currentValue ? "selected" : ""}>${opt}</option>`
                ).join("");

                return `
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
            } else {
                return `<span data-ocn="${docname}">${frappe.utils.escape_html(currentValue)}</span>`;
            }
        }

        return html;
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

        // setTimeout(() => {
        //     const columns = report.columns() || [];
        //     columns.forEach(c => {
        //         if (["status", "folding"].includes((c.fieldname || "").toLowerCase())) {
        //             c.editable = 1;
        //         }
        //     });
        // }, 500);

        const save = frappe.utils.debounce(function (e) {
            const $el = $(e.currentTarget);
            const docname = $el.data("docname");
            const doctype = $el.data("doctype");
            const fieldname = $el.data("fieldname");
            const newValue = $el.val();
            const oldValue = $el.data("old-value");

            // Prevent unnecessary save if no change
            if (newValue === oldValue) return;

            // Handle Status Change
            if (fieldname === "custom_consumption_status") {
                const statusOrder = ["Prepared", "Verified", "Pending for Approval", "Approved"];
                const oldIndex = statusOrder.indexOf(oldValue);
                const newIndex = statusOrder.indexOf(newValue);

                // Validate: must move forward by exactly 1 step (or stay same, but we already skip same)
                if (newIndex === -1) {
                    frappe.msgprint(__("Invalid status selected."));
                    $el.val(oldValue);
                    return;
                }

                if (newIndex < oldIndex) {
                    frappe.msgprint(__("Status cannot move backward."));
                    $el.val(oldValue);
                    return;
                }

                if (newIndex > oldIndex + 1) {
                    frappe.msgprint(__("Status can only move to the next stage."));
                    $el.val(oldValue);
                    return;
                }

                // Special: Only Factory Manager can approve
                if (newValue === "Approved") {
                    if (!this.hasRole("Factory Manager")) {
                        frappe.msgprint(__("Only Factory Manager can set status to 'Approved'"));
                        $el.val(oldValue);
                        return;
                    }

                    // Validation: all required fields must be filled across all rows of this OCN
                    const relatedRows = report.data.filter(row => row.ocn === docname);
                    const requiredFields = [
                        { key: "fabric_ordered", label: "Fabric Ordered" },
                        { key: "fabric_issued", label: "Fabric Issued" },
                        { key: "folding", label: "Folding" },
                        { key: "end_bit", label: "End Bit" },
                        { key: "file_consumption", label: "File Consumption" },
                        { key: "actual_consumption", label: "Actual Consumption" }
                    ];

                    const missingFields = [];
                    relatedRows.forEach(row => {
                        requiredFields.forEach(field => {
                            const val = row[field.key];
                            if (val === null || val === undefined || String(val).trim() === "") {
                                if (!missingFields.includes(field.label)) {
                                    missingFields.push(field.label);
                                }
                            }
                        });
                    });

                    if (missingFields.length > 0) {
                        const message = `Cutting flow not completed. Cannot approve.<br><br>Missing: <b>${missingFields.join(", ")}</b>`;
                        frappe.msgprint({
                            title: __('Approval Blocked'),
                            indicator: 'red',
                            message: __(message)
                        });
                        $el.val(oldValue);
                        return;
                    }

                    // Show confirmation
                    frappe.confirm(
                        __("Approve this Sales Order? This will finalize the cutting status."),
                        () => {
                            $el.css("opacity", 0.6);
                            frappe.call({
                                method: "cuttingx.cuttingx.api.approve_consumption_status.approve_consumption_status",
                                args: { sales_order: docname },
                                callback: (r) => {
                                    if (!r.exc) {
                                        frappe.show_alert({ message: __("Approved!"), indicator: "green" });
                                        $el.data("old-value", "Approved");
                                        report.refresh();
                                    } else {
                                        $el.val(oldValue);
                                    }
                                },
                                always: () => $el.css("opacity", 1)
                            });
                        },
                        () => $el.val(oldValue)
                    );
                    return;
                }

                // For non-Approved status changes: allow direct save
                $el.css("opacity", 0.6);
                frappe.call({
                    method: "frappe.client.set_value",
                    args: { doctype, name: docname, fieldname, value: newValue },
                    callback(r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Status updated"), indicator: "green" });
                            $el.data("old-value", newValue);

                            // ✅ UPDATE THE DOM DIRECTLY TO REFLECT NEW STATUS
                            // Find all cells in this OCN with status column and update their display
                            const ocnRows = report.page.wrapper.find(`[data-ocn="${docname}"]`);
                            ocnRows.each(function() {
                                const $row = $(this);
                                const $statusCell = $row.find('.report-status-select').closest('td');
                                if ($statusCell.length) {
                                    // Update the <select> value and selected option
                                    $statusCell.find('select').val(newValue).trigger('change');

                                    // Also update the fallback span if any (for non-first rows)
                                    $statusCell.find('span').text(newValue);
                                }
                            });

                            // Optional: also update report.data for future reference
                            report.data.forEach(row => {
                                if (row.ocn === docname) {
                                    row.status = newValue;
                                }
                            });

                        } else {
                            frappe.msgprint(__("Failed to update status"));
                            $el.val(oldValue);
                        }
                    },
                    always() {
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
