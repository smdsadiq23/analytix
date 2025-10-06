frappe.query_reports["Scan Log Report"] = {
  filters: [
    { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
    { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
    { fieldname: "sales_order", label: __("Sales Order"), fieldtype: "Link", options: "Sales Order" },
    { fieldname: "work_order", label: __("Work Order"), fieldtype: "Link", options: "Work Order" }
  ],

  onload(report) {
    // initial mount, with retries until header appears
    ensureBreadcrumb(report);

    // also set a tiny delay re-run (covers slow first paints)
    setTimeout(() => ensureBreadcrumb(report), 300);
    setTimeout(() => ensureBreadcrumb(report), 1000);
  }
};

function ensureBreadcrumb(report) {
  const $wrapper = $(report?.page?.wrapper || report?.page?.$wrapper || []);
  const $titleArea = report?.page?.$title_area || $wrapper.find(".page-title").first();
  if (!$titleArea || !$titleArea.length) return; // header not ready yet

  const $head = $titleArea.closest(".page-head");
  const $existing = $head.prev(".cx-breadcrumb-bar");
  if (!$existing.length) {
    const $bar = $(`		
      <div class="cx-breadcrumb-bar" style="
        padding: 8px 16px;
        background: #f9fafb;
        border-bottom: 1px solid #e5e7eb;
        font-size: 14px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
      ">
        <a href="/app/kpi-hub" style="color: #1f2937; text-decoration: none;">KPI Hub</a>
        <span style="color:#9ca3af;">›</span>
        <span style="color:#6b7280;">Scan Log Report</span>
      </div>
    `);
    // Put the breadcrumb directly above the page head so it survives most re-renders
    $bar.insertBefore($head);
    // tighten spacing
    $titleArea.css("margin-top", "0");

    // Guard it with a MutationObserver (if the head gets re-rendered, we re-mount)
    const host = $head.parent()[0];
    if (host) {
      const mo = new MutationObserver(() => {
        if (!$head.prev(".cx-breadcrumb-bar").length) {
          // re-add if removed
          ensureBreadcrumb(report);
        }
      });
      mo.observe(host, { childList: true });
    }
  }
}