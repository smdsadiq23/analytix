// Copyright (c) 2026 Your Company
// Enables inline editing of Remarks field in report


// Copyright (c) 2026 Your Company
// Enables inline editing of Remarks field in report

frappe.query_reports["Gate Inward vs GRN"] = {
  formatter(value, row, column, data, default_formatter) {
    const html = default_formatter(value, row, column, data, default_formatter);
    if (!data) return html;

    const isRemarks = 
      (column.fieldname === "remarks") || 
      (column.label === "Remarks");

    // Only make remarks editable if Purchase Receipt exists AND is in draft (not submitted)
    if (isRemarks && data.purchase_receipt) {
      const safe = frappe.utils.escape_html(value || "");
      const docname = data.purchase_receipt;
      const isSubmitted = data.pr_docstatus === 1; // Check if submitted
      
      // If submitted, show read-only text
      if (isSubmitted) {
        return `<div style="padding:4px 6px; color:#6c757d;">${safe || '<span class="text-muted">No remarks</span>'}</div>`;
      }
      
      // If draft, show editable textarea
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
    const $wrap = report.page.wrapper;

		CX.mountBreadcrumb({
			wrapper: report.page.wrapper || report.page.$wrapper,
			trail: [{ label: "KPI Hub", href: "/app/kpi-hub" }, { label: "Gate Inward Entry vs GRN" }],
		});

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
          doctype: "Purchase Receipt",
          name: $el.attr("data-docname"),
          fieldname: "remarks",
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