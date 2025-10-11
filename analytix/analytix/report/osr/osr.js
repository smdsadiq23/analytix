// Copyright (c) 2025, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["OSR"] = {
  formatter(value, row, column, data, default_formatter) {
    const html = default_formatter(value, row, column, data, default_formatter);
    if (!data) return html;

    const editableFields = [
      { fieldname: "iapl_fob", custom_field: "iapl_fob", type: "Currency" },
      { fieldname: "iapl_margin", custom_field: "iapl_margin", type: "Currency" },
      { fieldname: "shipped_date", custom_field: "shipped_date", type: "Date" },
      { fieldname: "shipment_status", custom_field: "shipment_status", type: "Select", options: ["Completed"] },
      { fieldname: "remarks_sandeep", custom_field: "remarks_sandeep", type: "Data" },
      { fieldname: "remarks_logesh", custom_field: "remarks_logesh", type: "Data" },
      { fieldname: "approved_by_muthu", custom_field: "approved_by_muthu", type: "Select", options: ["Approved"] }
    ];

    const currentField = editableFields.find(f => f.fieldname === column.fieldname);
    if (!currentField) return html;

    let safeValue = value != null ? value : "";
    if (typeof safeValue === "number" && isNaN(safeValue)) safeValue = "";

    const ocn = data.ocn;
    const style_ref = data.style_ref;

    if (!ocn || !style_ref) return html;

    const esc = (str) => frappe.utils.escape_html(String(str || ""));

    if (currentField.type === "Date") {
      const dateVal = safeValue ? frappe.datetime.user_to_str(safeValue) : "";
      return `
        <input 
          type="date"
          class="report-editable-input"
          data-ocn="${esc(ocn)}"
          data-style-ref="${esc(style_ref)}"
          data-custom-field="${currentField.custom_field}"
          value="${dateVal}"
          style="width:100%; box-sizing:border-box; padding:4px 6px;"
        />
      `;
    } else if (currentField.type === "Select") {
      const selected = currentField.options.includes(safeValue) ? safeValue : "";
      let optionsHTML = `<option value="">---</option>`;
      for (let opt of currentField.options) {
        optionsHTML += `<option value="${esc(opt)}" ${opt === selected ? 'selected' : ''}>${esc(opt)}</option>`;
      }
      return `
        <select 
          class="report-editable-input"
          data-ocn="${esc(ocn)}"
          data-style-ref="${esc(style_ref)}"
          data-custom-field="${currentField.custom_field}"
          style="width:100%; box-sizing:border-box; padding:4px 6px;"
        >
          ${optionsHTML}
        </select>
      `;
    } else {
      return `
        <input 
          type="text"
          class="report-editable-input"
          data-ocn="${esc(ocn)}"
          data-style-ref="${esc(style_ref)}"
          data-custom-field="${currentField.custom_field}"
          data-fieldtype="${currentField.type}"
          value="${esc(String(safeValue))}"
          style="width:100%; box-sizing:border-box; padding:4px 6px;"
        />
      `;
    }
  },

  onload(report) {
    if (window.CX && CX.mountBreadcrumb) {
      CX.mountBreadcrumb({
        wrapper: report.page.wrapper || report.page.$wrapper,
        trail: [
          { label: "KPI Hub", href: "/app/kpi-hub" },
          { label: "OSR" }
        ]
      });
    }

    const $wrap = report.page.wrapper;

	const save = frappe.utils.debounce(async function (e) {
		const $el = $(e.currentTarget);
		const ocn = $el.attr("data-ocn");
		const style_ref = $el.attr("data-style-ref");
		const customField = $el.attr("data-custom-field");
		const fieldType = $el.attr("data-fieldtype");

		if (!ocn || !style_ref) {
			frappe.throw(__("Missing OCN or Style Reference"));
			return;
		}

		let value = $el.is("select") ? $el.val() : $el.val();
		if (fieldType === "Currency") {
			value = value ? flt(value.replace(/,/g, "")) : null;
		} else if (fieldType === "Date") {
			value = value || null;
		}

		$el.css("opacity", 0.6);

		try {
			// ✅ Use get_list to safely fetch existing record
			const records = await frappe.db.get_list("Order Style Tracker", {
			filters: {
				sales_order: ocn,
				style: style_ref
			},
			fields: ["name"],
			limit: 1
			});

			let doc;
			if (records.length > 0) {
			doc = await frappe.db.get_doc("Order Style Tracker", records[0].name);
			} else {
			doc = {
				doctype: "Order Style Tracker",
				sales_order: ocn,
				style: style_ref
			};
			}

			doc[customField] = value;

			await frappe.call({
			method: "frappe.client.save",
			args: { doc: doc }
			});

			frappe.show_alert({ message: __("Saved"), indicator: "green" });

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

    $wrap.on("change", ".report-editable-input", save);
    $wrap.on("blur", "input.report-editable-input", save);
  }
};