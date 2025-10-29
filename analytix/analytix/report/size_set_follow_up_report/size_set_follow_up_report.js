// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Size Set Follow-up Report"] = {
		onload(report) {
		CX.mountBreadcrumb({
			wrapper: report.page.wrapper || report.page.$wrapper,
			trail: [
				{ label: "KPI Hub", href: "/app/kpi-hub" },
				{ label: "Size Set Follow-up Report" }
			]
		});   
				
        const $wrap = report.page.wrapper;

        // Add debounce for save
        const save = frappe.utils.debounce((e) => {
            const $el = $(e.currentTarget);
            const docname = $el.data("docname");
            const value = $el.val();

            $el.css("opacity", 0.6);
            frappe.call({
                method: "frappe.client.set_value",
                args: {
                    doctype: "Sales Order",
                    name: docname,
                    fieldname: "custom_size_set_status",
                    value: value
                },
                callback(r) {
                    if (!r.exc) {
                        frappe.show_alert({ message: __("Saved"), indicator: "green" });
                        $el.data("old-value", value);
                    } else {
                        frappe.msgprint(__("Save failed"));
                    }
                },
                always() {
                    $el.css("opacity", 1);
                }
            });
        }, 600);

        // Track original value on focus
        $wrap.on("focus", ".report-status-select", function () {
            $(this).data("old-value", $(this).val());
        });

        // Save on change
        $wrap.on("change", ".report-status-select", save);
    },

    formatter(value, row, column, data, default_formatter) {
        const html = default_formatter(value, row, column, data, default_formatter);
        if (!data || column.fieldname !== "custom_size_set_status") return html;

        const docname = data.ocn;
        const currentValue = value || "Under checking";

        const options = ["Under Checking", "Awaiting Pattern", "Sewing Pending", "Completed"]
            .map(opt => `<option value="${opt}" ${opt === currentValue ? "selected" : ""}>${opt}</option>`)
            .join("");

        return `
            <select class="report-status-select"
                    data-docname="${docname}"
                    style="width:100%; padding:4px; border-radius:4px;">
                ${options}
            </select>
        `;
    }
};
