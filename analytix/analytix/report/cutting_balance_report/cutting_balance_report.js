// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt


frappe.query_reports["Cutting Balance Report"] = {
  formatter(value, row, column, data, default_formatter) {
    const html = default_formatter(value, row, column, data, default_formatter);
    if (!data) return html;

    const isRemarks = 
      (column.fieldname === "remarks") || 
      (column.label === "Remarks");

    if (isRemarks) {
      const safe = frappe.utils.escape_html(value || "");
      const docname = data.ocn; // Sales Order name
      return `
        <textarea class="report-remark-input"
                  data-docname="${docname}"
                  rows="2"
                  style="width:100%; box-sizing:border-box; padding:4px 6px; resize:vertical;">${safe}</textarea>
      `;
    }
    return html;
  },

  onload(report) {
    CX.mountBreadcrumb({
    wrapper: report.page.wrapper || report.page.$wrapper,
    trail: [
        { label: "KPI Hub", href: "/app/kpi-hub" },
        { label: "Cutting Balance Report" }
    ]
    });   

    const $wrap = report.page.wrapper;

    // Ensure Remarks column is treated as editable text
    (report.columns || []).forEach(col => {
      if (col.fieldname === "remarks") {
        col.fieldtype = "Data";
        col.align = "left";
      }
    });

    const save = frappe.utils.debounce(function (e) {
      const $el = $(e.currentTarget);
      $el.css("opacity", 0.6);
      frappe.call({
        method: "frappe.client.set_value",
        args: {
          doctype: "Sales Order",
          name: $el.attr("data-docname"),
          fieldname: "custom_report_remarks",
          value: $el.val()
        },
        callback() {
          frappe.show_alert({ message: __("Remarks saved"), indicator: "green" });
        },
        always() {
          $el.css("opacity", 1);
        }
      });
    }, 500);

    $wrap.on("input", ".report-remark-input", save);
    $wrap.on("blur", ".report-remark-input", save);
  }
};