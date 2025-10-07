// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Order Completion Report"] = {
  formatter(value, row, column, data, default_formatter) {
    const html = default_formatter(value, row, column, data, default_formatter);
    if (!data) return html;

    const editableFields = [
      { fieldname: "good_garments", custom_field: "custom_good_garments" },
      { fieldname: "missing_units", custom_field: "custom_missing_units" },
      { fieldname: "fob", custom_field: "custom_fob" }
    ];

    const currentField = editableFields.find(f => f.fieldname === column.fieldname);
    if (!currentField) return html;

	// ✅ Extract RAW numeric value (especially for Currency)
	let rawValue = value;
	if (column.fieldtype === "Currency" && typeof value === "string") {
		// Remove HTML tags and currency symbols
		const temp = document.createElement("div");
		temp.innerHTML = value;
		const text = temp.textContent || temp.innerText || "";
		// Extract number from "₹ 1,250.50" → "1250.50"
		rawValue = text.replace(/[^\d.-]/g, "");
		if (rawValue === "") rawValue = null;
	}	

	const safeValue = rawValue != null ? rawValue : "";
	const docname = data.ocn;
	const itemCode = data.style;

    let inputType = "number";
    if (column.fieldtype === "Currency") {
      inputType = "text";
    }

    return `
      <input 
        type="${inputType}"
        class="report-editable-input"
        data-sales-order="${docname}"
        data-item-code="${itemCode}"
        data-custom-field="${currentField.custom_field}"
        data-fieldtype="${column.fieldtype}"
        value="${safeValue}"
        style="width:100%; box-sizing:border-box; padding:4px 6px;"
      />
    `;
  },

  onload(report) {
	CX.mountBreadcrumb({
	wrapper: report.page.wrapper || report.page.$wrapper,
	trail: [
		{ label: "KPI Hub", href: "/app/kpi-hub" },
		{ label: "Order Completion Report" }
	]
	});

    const $wrap = report.page.wrapper;

    (report.columns || []).forEach(col => {
      if (["good_garments", "missing_units", "fob"].includes(col.fieldname)) {
        col.fieldtype = col.fieldtype || "Float";
      }
    });

    const save = frappe.utils.debounce(async function (e) {
      const $el = $(e.currentTarget);
      const salesOrder = $el.attr("data-sales-order");
      const itemCode = $el.attr("data-item-code");
      const customField = $el.attr("data-custom-field");
      let value = $el.val();

      // Parse value
      if ($el.attr("data-fieldtype") === "Float" || $el.attr("data-fieldtype") === "Int") {
        value = value === "" ? null : flt(value);
      } else if ($el.attr("data-fieldtype") === "Currency") {
        if (value) {
          value = value.replace(/,/g, "");
          value = value === "" ? null : flt(value);
        } else {
          value = null;
        }
      }

      $el.css("opacity", 0.6);

      try {
        // ✅ STEP 1: Fetch the full Sales Order
        const soDoc = await frappe.db.get_doc("Sales Order", salesOrder);
        
        // ✅ STEP 2: Find and update the correct item row
        let itemFound = false;
        for (let item of soDoc.items) {
          if (item.item_code === itemCode) {
            item[customField] = value;
            itemFound = true;
            break;
          }
        }

        if (!itemFound) {
          frappe.throw(__("Item {0} not found in Sales Order {1}", [itemCode, salesOrder]));
          return;
        }

        // ✅ STEP 3: Save the ENTIRE parent document (this updates child table)
        await frappe.call({
          method: "frappe.client.save",
          args: {
            doc: soDoc
          }
        });

        frappe.show_alert({ message: __("Value saved"), indicator: "green" });
      } catch (error) {
        console.error("Save failed:", error);
        frappe.show_alert({ 
          message: __("Save failed: {0}", [error.message || "Unknown error"]), 
          indicator: "red" 
        });
      } finally {
        $el.css("opacity", 1);
      }
    }, 800);

    $wrap.on("input", ".report-editable-input", save);
    $wrap.on("blur", ".report-editable-input", save);
  }
};