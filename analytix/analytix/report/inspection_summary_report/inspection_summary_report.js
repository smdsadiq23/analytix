// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Inspection Summary Report"] = {
    filters: [
        { fieldname: "company",   label: "Company",   fieldtype: "Link", options: "Company" },
        { fieldname: "from_date", label: "From Date", fieldtype: "Date", default: frappe.datetime.month_start() },
        { fieldname: "to_date",   label: "To Date",   fieldtype: "Date", default: frappe.datetime.get_today() },
    ],

    after_datatable_render(report) {
        const $page = $(report.page.wrapper);

        // pull labels & values from the result rows
        const rows = Array.isArray(report.data) ? report.data : [];
        const labels = rows.map(r => r.status);
        const fabricValues = rows.map(r => Number(r.fabric_count || 0));
        const trimsValues  = rows.map(r => Number(r.trims_count  || 0));

        // find chart holders from message HTML
        const $fabricHost = $page.find("#cx-fabric-pie");
        const $trimsHost  = $page.find("#cx-trims-pie");

        // destroy previous charts if any
        try {
        report.__cxFabricPie && report.__cxFabricPie.destroy();
        report.__cxTrimsPie && report.__cxTrimsPie.destroy();
        } catch {}

        // draw pie helper
        const drawPie = (el, name, lbls, vals) =>
        new frappe.Chart(el, {
            type: "pie",
            data: { labels: lbls, datasets: [{ name, values: vals }] },
            height: 260
        });

        if ($fabricHost.length) {
        $fabricHost.empty();
        report.__cxFabricPie = drawPie($fabricHost[0], __("Fabric"), labels, fabricValues);
        }
        if ($trimsHost.length) {
        $trimsHost.empty();
        report.__cxTrimsPie = drawPie($trimsHost[0], __("Trims"), labels, trimsValues);
        }
    }
};
