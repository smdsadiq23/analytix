// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Orders in Hand"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: new Date().getFullYear() + "-01-01",
            reqd: 0
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 0
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data, default_formatter);

        const fieldname = column.fieldname;
        if (fieldname === "shipped_qty") {
            const shippedQty = parseFloat(data.shipped_qty) || 0;
            const salesOrder = data.sales_order_no || "";
            const styleNo = data.style_no || "";

            return `
                <div class="editable-shipped-qty"
                     data-sales-order="${frappe.utils.escape_html(salesOrder)}"
                     data-style-no="${frappe.utils.escape_html(styleNo)}"
                     data-current-value="${shippedQty}">
                    <input type="number"
                           class="shipped-qty-input"
                           value="${shippedQty}"
                           min="0"
                           step="0.01"
                           style="width:80px;padding:2px;border:1px solid #ccc;">
                </div>
            `;
        }

        return default_formatter(value, row, column, data, default_formatter);
    },

    onload: function(report) {
        CX.mountBreadcrumb({
            wrapper: report.page.wrapper || report.page.$wrapper,
            trail: [
                { label: "KPI Hub", href: "/app/kpi-hub" },
                { label: "Orders in Hand" }
            ]
        });

        report.page.add_inner_button(__("Refresh Report"), () => report.refresh());

        const $wrap = report.page.wrapper;

        const save = frappe.utils.debounce(function(e) {
            const $input = $(e.currentTarget);
            const $container = $input.closest('.editable-shipped-qty');
            const sales_order_no = $container.data('sales-order');
            const style_no = $container.data('style-no');
            const current_value = parseFloat($container.data('current-value')) || 0;
            const new_value = parseFloat($input.val()) || 0;

            if (new_value === current_value) return;

            $input.prop('disabled', true).css('opacity', 0.6);

            frappe.call({
                method: "analytix.analytix.report.orders_in_hand.orders_in_hand.save_shipped_qty",
                args: {
                    data: {
                        sales_order_no: sales_order_no,
                        style_no: style_no,
                        shipped_qty: new_value
                    }
                },
                callback: function(r) {
                    $input.prop('disabled', false).css('opacity', 1);
                    if (r.message && r.message.status === "success") {
                        frappe.show_alert({ message: __("Saved"), indicator: 'green' }, 2);
                        $container.data('current-value', new_value);

                        // Update adjacent cells
                        const $row = $container.closest('tr');
                        $row.find('[data-fieldname="shipped_bal"] .dt-cell__content').text(
                            format_number(r.message.shipped_bal || 0)
                        );
                        $row.find('[data-fieldname="overdue_status"] .dt-cell__content').text(
                            r.message.overdue_status || ''
                        );

                        // Update in-memory data
                        const rowIndex = $row.index();
                        if (report.data && report.data[rowIndex]) {
                            report.data[rowIndex].shipped_qty = new_value;
                            report.data[rowIndex].shipped_bal = r.message.shipped_bal;
                            report.data[rowIndex].overdue_status = r.message.overdue_status;
                            report.data[rowIndex].ship_record = r.message.record;
                        }
                    } else {
                        let msg = __("Save failed");
                        if (r.exc) msg = r.exc[0]?.split('\n')[0] || r.exc[0];
                        else if (r.message?.message) msg = r.message.message;
                        frappe.show_alert({ message: msg, indicator: 'red' }, 5);
                        $input.val(current_value);
                    }
                },
                error: function() {
                    $input.prop('disabled', false).css('opacity', 1);
                    frappe.show_alert({ message: __("Network error"), indicator: 'red' }, 5);
                    $input.val(current_value);
                }
            });
        }, 500);

        $wrap.on('focus', '.shipped-qty-input', function() {
            $(this).data('old-value', $(this).val());
        });

        $wrap.on('blur keyup', '.shipped-qty-input', function(e) {
            if (e.type === 'keyup' && e.key !== 'Enter') return;
            save(e);
        });
    }
};

function format_number(value) {
    if (value == null || value === '') return '0';
    const num = parseFloat(value);
    return isFinite(num) ? num.toFixed(2) : '0';
}