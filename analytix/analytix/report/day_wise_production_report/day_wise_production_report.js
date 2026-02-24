// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Day Wise Production Report"] = {
	"filters": [

	],

  onload(report) {
    CX.mountBreadcrumb({
      wrapper: report.page.wrapper || report.page.$wrapper,
      trail: [
        { label: "KPI Hub", href: "/app/kpi-hub" },
        { label: "Day Wise Production Report" }
      ]
    });
  }	
};