frappe.query_reports["Scan Log Report"] = {
  filters: [
    { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
    { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
    { fieldname: "sales_order", label: __("Sales Order"), fieldtype: "Link", options: "Sales Order" },
    { fieldname: "work_order", label: __("Work Order"), fieldtype: "Link", options: "Work Order" }
  ],

  onload(report) {
    CX.mountBreadcrumb({
      wrapper: report.page.wrapper || report.page.$wrapper,
      trail: [
        { label: "KPI Hub", href: "/app/kpi-hub" },
        { label: "Scan Log Report" }
      ]
    });
  }
};
