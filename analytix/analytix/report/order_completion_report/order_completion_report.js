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

    let rawValue = value;
    if (column.fieldtype === "Currency" && typeof value === "string") {
      const temp = document.createElement("div");
      temp.innerHTML = value;
      const text = temp.textContent || temp.innerText || "";
      rawValue = text.replace(/[^\d.-]/g, "");
      if (rawValue === "") rawValue = null;
    }

    const safeValue = rawValue != null ? rawValue : "";
    const docname = data.ocn;
    const itemCode = data.style;

    // ✅ Embed data for FOB field only
    let extraAttrs = "";
    if (currentField.fieldname === "fob") {
      extraAttrs = `
        data-order-qty-plus="${flt(data.order_qty_plus)}"
        data-cut-qty="${flt(data.cut_qty)}"
        data-ship-qty="${flt(data.ship_qty)}"
      `;
    }

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
        ${extraAttrs}
        value="${frappe.utils.escape_html(String(safeValue))}"
        style="width:100%; box-sizing:border-box; padding:4px 6px;"
      />
    `;
  },

  onload(report) {
    if (window.CX && CX.mountBreadcrumb) {
      CX.mountBreadcrumb({
        wrapper: report.page.wrapper || report.page.$wrapper,
        trail: [
          { label: "KPI Hub", href: "/app/kpi-hub" },
          { label: "Order Completion Report" }
        ]
      });
    }

    const $wrap = report.page.wrapper;

    // ✅ COLUMN INDICES FOR DATATABLE v2 (1-based)
    const SHORT_CUTTING_LOSS_COL = 23; // adjust if needed
    const VALUE_LOSS_COL = 24;        // adjust if needed

    const updateLossCell = ($row, colIndex, value) => {
      const $cell = $row.find(`.dt-cell__content--col-${colIndex}`);
      if ($cell.length) {
        if (value !== null && !isNaN(value)) {
          $cell.html(frappe.format(value, { fieldtype: "Currency" }));
        } else {
          $cell.html("");
        }
      }
    };

    const recalculateLosses = ($input) => {
      try {
        const order_qty_plus = flt($input.attr("data-order-qty-plus"));
        const cut_qty = flt($input.attr("data-cut-qty"));
        const ship_qty = flt($input.attr("data-ship-qty"));
        const fobStr = $input.val();
        const fob = fobStr ? flt(fobStr.replace(/,/g, "")) : null;

        let short_cutting_loss = null;
        let value_loss = null;

        if (fob > 0) {
          if (cut_qty > 0) {
            short_cutting_loss = Math.max(0, (order_qty_plus - cut_qty) * fob);
          }
          if (ship_qty > 0) {
            value_loss = Math.max(0, (cut_qty - ship_qty) * fob);
          }
        }

        const $row = $input.closest('.dt-row'); // DataTable v2 uses .dt-row
        updateLossCell($row, SHORT_CUTTING_LOSS_COL, short_cutting_loss);
        updateLossCell($row, VALUE_LOSS_COL, value_loss);
      } catch (e) {
        console.warn("Recalc failed:", e);
      }
    };

    const save = frappe.utils.debounce(async function (e) {
      const $el = $(e.currentTarget);
      const $row = $el.closest('.dt-row');
      const salesOrder = $el.attr("data-sales-order");
      const itemCode = $el.attr("data-item-code");
      const customField = $el.attr("data-custom-field");
      let value = $el.val();

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
        const soDoc = await frappe.db.get_doc("Sales Order", salesOrder);
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

        await frappe.call({
          method: "frappe.client.save",
          args: { doc: soDoc }
        });

        frappe.show_alert({ message: __("Value saved"), indicator: "green" });
        
        if (customField === "custom_fob") {
          $el.val(value);
          recalculateLosses($el);
        }
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

    // ✅ Live update
    $wrap.on("input", '.report-editable-input[data-custom-field="custom_fob"]', function() {
      recalculateLosses($(this));
    });

    $wrap.on("input", ".report-editable-input", save);
    $wrap.on("blur", ".report-editable-input", save);
  }
};