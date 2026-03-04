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

        const isStatus     = fieldname === "status";
        const isApproval   = fieldname === "approval";
        const isCutPct     = fieldname === "cut_completion_pct";
        const isDifference = fieldname === "difference";

        const rowStatus = data.status || "";

        const wrapWithStatusBg = (content) => {
            let bg = "";
            if (rowStatus === "Inprogress") bg = "#fff9c4";
            else if (rowStatus === "Completed") bg = "#c8e6c9";
            else if (rowStatus === "Verified")  bg = "#bbdefb";
            if (!bg) return content;
            return `<span class="cut-status-bg" style="display:block;background-color:${bg};">${content}</span>`;
        };

        // Cut Completion %
        if (isCutPct) {
            const pct = Number(data.cut_completion_pct || 0);
            return wrapWithStatusBg(`<span>${fmt(pct, 2)}%</span>`);
        }

        // ✅ Difference cell — embed size-wise balance JSON as a data attribute for hover popup
        if (isDifference) {
            let sizeData = [];
            try { sizeData = JSON.parse(data.size_wise_balance || "[]"); } catch (_) {}
            const encoded = frappe.utils.escape_html(JSON.stringify(sizeData));
            return wrapWithStatusBg(
                `<span class="ccr-diff-cell" data-size-wise="${encoded}" style="cursor:default;">${html}</span>`
            );
        }

        // ✅ Editable Status Dropdown
        if (isStatus) {
            const docname        = data.ocn;
            const currentValue   = rowStatus;
            const currentApproval = data.approval || "";
            const isVerifier     = this.hasRole("CCR Verifier");
            const canEditStatus  = isVerifier && docname && currentApproval !== "Approved";

            if (canEditStatus) {
                const options = ["Yet to Start", "Inprogress", "Completed", "Verified"].map(opt => {
                    const selected = opt === currentValue ? "selected" : "";
                    return `<option value="${opt}" ${selected}>${opt}</option>`;
                }).join("");

                return wrapWithStatusBg(`
                    <div data-ocn="${docname}">
                        <select class="report-status-select"
                                data-docname="${docname}"
                                data-doctype="Sales Order"
                                data-fieldname="custom_consumption_status"
                                style="width:100%; padding:4px; border-radius:4px;">
                            ${options}
                        </select>
                    </div>
                `);
            }
            return wrapWithStatusBg(`<span>${frappe.utils.escape_html(currentValue)}</span>`);
        }

        // ✅ Approval Column
        if (isApproval) {
            const docname         = data.ocn;
            if (!docname) return wrapWithStatusBg(html);

            const currentApproval  = data.approval || "";
            const withReplenishment = Number(data.with_replenishment || 0);
            const isFactoryManager  = this.hasRole("Factory Manager");

            let displayText = currentApproval;
            if (rowStatus === "Verified" && !currentApproval) {
                displayText = "Yet to Confirm";
            } else if (currentApproval === "Approved") {
                displayText = withReplenishment ? "App with Replenishment" : "Approved";
            }

            const canApprove = !currentApproval && rowStatus === "Verified" && isFactoryManager;

            if (canApprove) {
                return wrapWithStatusBg(`
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
                `);
            }
            return wrapWithStatusBg(`<span data-ocn="${docname}">${frappe.utils.escape_html(displayText)}</span>`);
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
            const $el      = $(e.currentTarget);
            const docname  = $el.data("docname");
            const doctype  = $el.data("doctype");
            const fieldname = $el.data("fieldname");
            const newValue  = $el.val();
            const oldValue  = $el.data("old-value");

            if (newValue === oldValue) return;

            // ✅ Handle Status Update
            if (fieldname === "custom_consumption_status") {
                if (!this.hasRole("CCR Verifier")) {
                    frappe.msgprint(__("You do not have permission to update cutting status."));
                    $el.val(oldValue);
                    return;
                }

                const row = (report.data || []).find(r => r.ocn === docname);
                if (!row) { frappe.msgprint(__("Row data not found.")); $el.val(oldValue); return; }
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
                        if (r.exc) { frappe.msgprint(__("Failed to update status.")); $el.val(oldValue); return; }
                        frappe.show_alert({ message: __("Status updated"), indicator: "green" });
                        $el.data("old-value", newValue);
                        (report.data || []).forEach(rw => { if (rw.ocn === docname) rw.status = newValue; });
                    },
                    always: () => { $el.css("opacity", 1); }
                });
                return;
            }

            // ✅ Handle Factory Manager Approval
            if (fieldname === "custom_approval") {
                if (!this.hasRole("Factory Manager")) {
                    frappe.msgprint(__("Only Factory Managers can approve."));
                    $el.val(oldValue);
                    return;
                }

                const row = (report.data || []).find(r => r.ocn === docname);
                if (!row) { frappe.msgprint(__("Row not found.")); $el.val(oldValue); return; }
                if (row.status !== "Verified") {
                    frappe.msgprint(__("Only 'Verified' status can be approved."));
                    $el.val(oldValue);
                    return;
                }
                if (newValue !== "Approved") { $el.val(oldValue); return; }

                $el.css("opacity", 0.6);

                frappe.call({
                    method: "frappe.client.set_value",
                    args: { doctype: "Sales Order", name: docname, fieldname: "custom_approval", value: "Approved" },
                    callback: (r1) => {
                        if (r1.exc) {
                            console.error("Approval update failed:", r1.exc);
                            frappe.msgprint(__("Failed to update approval."));
                            $el.val(oldValue); $el.css("opacity", 1);
                            return;
                        }
                        frappe.call({
                            method: "frappe.client.set_value",
                            args: { doctype: "Sales Order", name: docname, fieldname: "custom_approved_by", value: frappe.session.user },
                            callback: (r2) => {
                                if (r2.exc) console.error("Approved By update failed:", r2.exc);
                                frappe.call({
                                    method: "frappe.client.set_value",
                                    args: { doctype: "Sales Order", name: docname, fieldname: "custom_approved_on", value: frappe.datetime.now_datetime() },
                                    callback: (r3) => {
                                        if (r3.exc) console.error("Approved On update failed:", r3.exc);
                                        frappe.show_alert({ message: __("Approved"), indicator: "green" });
                                        $el.data("old-value", "Approved");
                                        (report.data || []).forEach(rw => {
                                            if (rw.ocn === docname) {
                                                rw.approval = "Approved";
                                                rw.custom_approved_by = frappe.session.user;
                                                rw.custom_approved_on = frappe.datetime.now_datetime();
                                            }
                                        });
                                        $el.closest("td").html(`<span>Approved</span>`);
                                        $el.css("opacity", 1);
                                    },
                                    always: () => { if (!r3 || r3.exc) $el.css("opacity", 1); }
                                });
                            },
                            always: () => {}
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
                always() { $el.css("opacity", 1); }
            });
        }.bind(this), 600);

        $wrap.on("focus", ".report-editable-field, .report-status-select", function () {
            $(this).data("old-value", $(this).val());
        });
        $wrap.on("blur",   ".report-editable-field",  save);
        $wrap.on("change", ".report-status-select",   save);

        // ─── Size-wise Balance hover popup ───────────────────────────────────────

        if (!document.getElementById("ccr-size-popup-style")) {
            const style = document.createElement("style");
            style.id = "ccr-size-popup-style";
            style.textContent = `
                #ccr-size-popup {
                    position: fixed;
                    z-index: 9999;
                    background: #fff;
                    border: 1px solid #d1d5db;
                    border-radius: 6px;
                    box-shadow: 0 4px 16px rgba(0,0,0,0.13);
                    padding: 10px 14px;
                    min-width: 180px;
                    pointer-events: none;
                    font-size: 12px;
                }
                #ccr-size-popup table {
                    border-collapse: collapse;
                    width: 100%;
                }
                #ccr-size-popup th {
                    text-align: right;
                    padding: 3px 8px;
                    background: #f3f4f6;
                    border-bottom: 1px solid #e5e7eb;
                    font-weight: 600;
                    color: #374151;
                }
                #ccr-size-popup th:first-child { text-align: left; }
                #ccr-size-popup td {
                    text-align: right;
                    padding: 3px 8px;
                    border-bottom: 1px solid #f3f4f6;
                    color: #111827;
                }
                #ccr-size-popup td:first-child { text-align: left; }
                #ccr-size-popup tfoot td {
                    border-top: 1px solid #e5e7eb;
                    border-bottom: none;
                    padding-top: 5px;
                    font-weight: 600;
                }
                #ccr-size-popup .popup-title {
                    font-weight: 700;
                    margin-bottom: 6px;
                    color: #1f2937;
                }
            `;
            document.head.appendChild(style);
        }

        let $popup = $("#ccr-size-popup");
        if (!$popup.length) {
            $popup = $('<div id="ccr-size-popup"></div>').appendTo(document.body).hide();
        }

        $wrap.on("mouseenter", ".ccr-diff-cell", function (e) {
            let sizeData = [];
            try { sizeData = JSON.parse($(this).attr("data-size-wise") || "[]"); } catch (_) {}
            if (!sizeData.length) return;

            const bodyRows = sizeData.map(s =>
                `<tr>
                    <td>${frappe.utils.escape_html(s.size || "—")}</td>
                    <td>${s.balance}</td>
                </tr>`
            ).join("");

            const totalBalance = sizeData.reduce((a, s) => a + (s.balance || 0), 0);

            $popup.html(`
                <div class="popup-title">Size-wise Balance</div>
                <table>
                    <thead>
                        <tr><th>Size</th><th>Balance</th></tr>
                    </thead>
                    <tbody>${bodyRows}</tbody>
                    <tfoot>
                        <tr>
                            <td>Total</td>
                            <td>${totalBalance}</td>
                        </tr>
                    </tfoot>
                </table>
            `);

            const offset = 12;
            let left = e.clientX + offset;
            let top  = e.clientY + offset;
            const popW = 200;
            const popH = 60 + sizeData.length * 26;

            if (left + popW > window.innerWidth)  left = e.clientX - popW - offset;
            if (top  + popH > window.innerHeight) top  = e.clientY - popH - offset;

            $popup.css({ left, top }).show();
        });

        $wrap.on("mouseleave", ".ccr-diff-cell", function () {
            $popup.hide();
        });
    },

    // ✅ Freeze first 5 columns after datatable renders
    after_datatable_render(datatable) {
        const numColumnsToFreeze = 5;
        const bodyScrollable = datatable.bodyScrollable;
        if (!bodyScrollable) return;

        bodyScrollable.addEventListener("scroll", (e) => {
            if (datatable._settingHeaderPosition) return;
            datatable._settingHeaderPosition = true;

            requestAnimationFrame(() => {
                const scrollLeft = e.target.scrollLeft;

                for (let i = 0; i < numColumnsToFreeze; i++) {
                    $(`.dt-cell--col-${i}`, datatable.header).each(function () {
                        this.style.transform = `translateX(${scrollLeft}px)`;
                        this.style.position  = "relative";
                        this.style.zIndex    = "10";
                        this.style.backgroundColor = "#f5f7fa";
                    });
                }

                $(bodyScrollable).find(".dt-row").each(function () {
                    const $cells = $(this).find(".dt-cell");
                    for (let i = 0; i < numColumnsToFreeze && i < $cells.length; i++) {
                        const cell = $cells[i];
                        cell.style.transform = `translateX(${scrollLeft}px)`;
                        cell.style.position  = "relative";
                        cell.style.zIndex    = "10";
                        cell.style.backgroundColor = "#ffffff";
                    }
                });

                const $footer = $(datatable.wrapper).find(".dt-footer");
                if ($footer.length) {
                    for (let i = 0; i < numColumnsToFreeze; i++) {
                        $(`.dt-cell--col-${i}`, $footer).each(function () {
                            this.style.transform = `translateX(${scrollLeft}px)`;
                            this.style.position  = "relative";
                            this.style.zIndex    = "10";
                            this.style.backgroundColor = "#fafbfc";
                        });
                    }
                }

                datatable._settingHeaderPosition = false;
            });
        });
    }
};