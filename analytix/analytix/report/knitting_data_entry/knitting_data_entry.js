// Copyright (c) 2026, CognitionX Logic India Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Knitting Data Entry"] = {
    filters: [],

    // ── Column formatters ─────────────────────────────────────────────────────
    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);

        const esc = (v) => frappe.utils.escape_html(String(v ?? ""));

        // ── Actual Qty: if blank → show rfid_qty as display label
        if (column.fieldname === "custom_actual_quantity") {
            const label = (value !== null && value !== undefined && value !== "") ? value : data.rfid_qty;
            return `<div class="kde-cell"
                        data-isl="${esc(data.isl_name)}"
                        data-fieldname="custom_actual_quantity"
                        data-fieldtype="Int"
                        data-label="Actual Qty"
                        data-value="${esc(value)}"
                        data-rfid-qty="${esc(data.rfid_qty)}">
                        <span class="kde-label">${esc(label)}</span>
                        <i class="fa fa-pencil kde-icon"></i>
                    </div>`;
        }

        // ── Operator
        if (column.fieldname === "custom_operator") {
            return `<div class="kde-cell"
                        data-isl="${esc(data.isl_name)}"
                        data-fieldname="custom_operator"
                        data-fieldtype="Link"
                        data-label="Operator"
                        data-value="${esc(value)}">
                        <span class="kde-label">${esc(value)}</span>
                        <i class="fa fa-pencil kde-icon"></i>
                    </div>`;
        }

        // ── Actual Weight: embed plnd_weight, tolerance and rfid_qty for client-side validation
        if (column.fieldname === "custom_actual_weight") {
            const display = (value !== null && value !== undefined && value !== "") ? value : "";
            return `<div class="kde-cell"
                        data-isl="${esc(data.isl_name)}"
                        data-fieldname="custom_actual_weight"
                        data-fieldtype="Float"
                        data-label="Actual Weight"
                        data-value="${esc(value)}"
                        data-plnd-weight="${esc(data.plnd_weight)}"
                        data-weight-tolerance="${esc(data.weight_tolerance)}"
                        data-rfid-qty="${esc(data.rfid_qty)}">
                        <span class="kde-label">${esc(display)}</span>
                        <i class="fa fa-pencil kde-icon"></i>
                    </div>`;
        }

        // ── Variance: read-only, red for any deviation, neutral for zero/empty
        if (column.fieldname === "variance") {
            return _varianceHTML(value, data.isl_name);
        }

        return default_formatter(value, row, column, data);
    },

    // ── onload ────────────────────────────────────────────────────────────────
    onload(report) {
        if (typeof CX !== "undefined" && CX.mountBreadcrumb) {
            CX.mountBreadcrumb({
                wrapper: report.page.wrapper || report.page.$wrapper,
                trail: [
                    { label: "KPI Hub", href: "/app/kpi-hub" },
                    { label: "Knitting Data Entry" },
                ],
            });
        }

        _injectStyles();

        if (!window._kdeListenerAttached) {
            window._kdeListenerAttached = true;

            document.addEventListener("click", function (e) {
                const cell = e.target.closest(".kde-cell");
                if (!cell) return;
                e.stopImmediatePropagation();
                _openDialog($(cell));
            }, true); // capture phase — fires before DataTable's handler
        }
    },
};

// ── Variance cell HTML ────────────────────────────────────────────────────────
// Both positive and negative variance = red (any deviation from plan is bad)

function _varianceHTML(value, islName) {
    const esc = (v) => frappe.utils.escape_html(String(v ?? ""));

    if (value === null || value === undefined || value === "") {
        return `<span class="kde-variance kde-var-empty" data-isl="${esc(islName)}">—</span>`;
    }

    const num     = flt(value);
    const rounded = Math.round(num * 1000) / 1000;
    const sign    = num > 0 ? "+" : "";
    const cls     = num === 0 ? "kde-var-zero" : "kde-var-diff"; // any deviation = red

    return `<span class="kde-variance ${cls}" data-isl="${esc(islName)}">${sign}${rounded}</span>`;
}

// ── Open dialog ───────────────────────────────────────────────────────────────

function _openDialog($cell) {
    const fieldname = $cell.attr("data-fieldname");
    const isl       = $cell.attr("data-isl");

    // ── Guard: actual_qty must be saved before actual_weight can be entered ──
    if (fieldname === "custom_actual_weight") {
        const $qtyCell = $(`.kde-cell[data-fieldname="custom_actual_quantity"][data-isl="${CSS.escape(isl)}"]`);
        const savedQty = $qtyCell.attr("data-value");

        if (!savedQty || savedQty === "" || savedQty === "null") {
            frappe.show_alert({
                message: __("Please save Actual Qty before entering Actual Weight."),
                indicator: "orange"
            }, 5);
            return; // block dialog from opening
        }
    }

    const fieldtype = $cell.attr("data-fieldtype");
    const label     = $cell.attr("data-label");
    const curValue  = $cell.attr("data-value");

    let fieldDef;
    if (fieldtype === "Link") {
        fieldDef = { fieldtype: "Link", options: "Employee", fieldname: "val", label: __(label), default: curValue };
    } else if (fieldtype === "Int") {
        fieldDef = { fieldtype: "Int", fieldname: "val", label: __(label), default: curValue !== "" ? cint(curValue) : "" };
    } else if (fieldtype === "Float") {
        fieldDef = { fieldtype: "Float", fieldname: "val", label: __(label), default: curValue !== "" ? flt(curValue) : "" };
    }

    const dlg = new frappe.ui.Dialog({
        title: __("Edit {0}", [label]),
        fields: [fieldDef],
        primary_action_label: __("Save"),
        async primary_action(vals) {
            dlg.hide();

            let newVal = vals.val;
            if (newVal === "" || newVal === undefined) newVal = null;
            if (fieldtype === "Int"   && newVal !== null) newVal = cint(newVal);
            if (fieldtype === "Float" && newVal !== null) newVal = flt(newVal);

            // ── Tolerance validation for actual_weight before saving ─────────
            if (fieldname === "custom_actual_weight" && newVal !== null) {
                const valid = _validateActualWeight(newVal, $cell);
                if (!valid) return; // descriptive error already shown inside
            }

            await _save(isl, fieldname, newVal, $cell);
        },
    });

    dlg.show();
}

// ── Tolerance validation ──────────────────────────────────────────────────────

function _validateActualWeight(actualWeight, $cell) {
    const isl        = $cell.attr("data-isl");
    const plndWeight = flt($cell.attr("data-plnd-weight"));
    const tolerance  = flt($cell.attr("data-weight-tolerance"));
    const rfidQty    = cint($cell.attr("data-rfid-qty"));

    // Read actual_qty that was saved — from the qty cell's data-value for this row
    const $qtyCell  = $(`.kde-cell[data-fieldname="custom_actual_quantity"][data-isl="${CSS.escape(isl)}"]`);
    const actualQty = cint($qtyCell.attr("data-value"));

    const lower = plndWeight - tolerance;
    const upper = plndWeight + tolerance;

    // ✅ Exact match — always allow
    if (actualWeight === plndWeight) return true;

    // ✅ Within tolerance band — allow
    if (actualWeight >= lower && actualWeight <= upper) return true;

    // ⚠️ Below band — allow only if actual_qty < rfid_qty
    if (actualWeight < lower) {
        if (actualQty < rfidQty) return true;
        frappe.show_alert({
            message: __(
                "Actual weight {0} is below the tolerance range ({1} to {2}). " +
                "Actual qty ({3}) must be less than RFID qty ({4}) to save this weight.",
                [actualWeight, lower.toFixed(3), upper.toFixed(3), actualQty, rfidQty]
            ),
            indicator: "red"
        }, 8);
        return false;
    }

    // ⚠️ Above band — allow only if actual_qty > rfid_qty
    if (actualWeight > upper) {
        if (actualQty > rfidQty) return true;
        frappe.show_alert({
            message: __(
                "Actual weight {0} exceeds the tolerance range ({1} to {2}). " +
                "Actual qty ({3}) must be greater than RFID qty ({4}) to save this weight.",
                [actualWeight, lower.toFixed(3), upper.toFixed(3), actualQty, rfidQty]
            ),
            indicator: "red"
        }, 8);
        return false;
    }

    return true;
}

// ── Persist + live-update cell and variance ───────────────────────────────────

async function _save(isl, fieldname, value, $cell) {
    $cell.css("opacity", 0.5);
    try {
        await frappe.call({
            method: "analytix.analytix.report.knitting_data_entry.knitting_data_entry.save_knitting_entry",
            args: { isl_name: isl, fieldname, value },
        });

        // ── Update this cell's label ─────────────────────────────────────────
        let displayVal = value ?? "";
        if (fieldname === "custom_actual_quantity") {
            displayVal = (value !== null && value !== undefined && value !== "")
                ? value
                : $cell.attr("data-rfid-qty");
        }
        $cell.attr("data-value", value ?? "");
        $cell.find(".kde-label").text(String(displayVal ?? ""));

        // ── Live-update Variance when Actual Weight changes ──────────────────
        if (fieldname === "custom_actual_weight") {
            const plndWeight = flt($cell.attr("data-plnd-weight"));
            const variance   = (value !== null) ? flt(value) - plndWeight : null;
            const $varCell   = $(`.kde-variance[data-isl="${CSS.escape(isl)}"]`);
            if ($varCell.length) {
                $varCell.replaceWith(_varianceHTML(variance, isl));
            }
        }

        frappe.show_alert({ message: __("Saved"), indicator: "green" }, 2);
    } catch (err) {
        console.error("Save failed:", err);
        frappe.show_alert({ message: __("Save failed"), indicator: "red" }, 3);
    } finally {
        $cell.css("opacity", 1);
    }
}

// ── Styles ────────────────────────────────────────────────────────────────────
function _injectStyles() {
    if (document.getElementById("kde-styles")) return;
    const s = document.createElement("style");
    s.id = "kde-styles";
    s.textContent = `
        /* ── Editable cells ── */
        .kde-cell {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            width: 100%;
            cursor: pointer;
            padding: 2px 4px;
            border-radius: 4px;
            transition: background 0.15s;
        }
        .kde-cell:hover { background: #eef0ff; }

        .kde-label {
            flex: 1;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .kde-icon {
            font-size: 10px;
            color: #bbb;
            flex-shrink: 0;
            transition: color 0.15s;
        }
        .kde-cell:hover .kde-icon { color: #5e64ff; }

        /* ── Variance chip ── */
        .kde-variance {
            display: inline-block;
            padding: 1px 8px;
            border-radius: 10px;
            font-size: var(--text-sm, 12px);
            font-weight: 500;
            letter-spacing: 0.02em;
        }
        .kde-var-empty { color: #aaa; }
        .kde-var-zero  { background: #f0f0f0; color: #555; }
        .kde-var-diff  { background: #fff0f0; color: #d32f2f; } /* any deviation = red */
    `;
    document.head.appendChild(s);
}