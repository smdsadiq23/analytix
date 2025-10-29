frappe.pages["kpi-hub"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "KPI Hub",
		single_column: true,
	});
	const $root = $(wrapper).find(".layout-main-section");

	const $toolbar = $(`
    <div class="d-flex align-items-center" style="margin-top:12px; gap:8px;">
      <input type="text" class="form-control" placeholder="Search dashboards..." style="max-width:280px;">
      <div class="grp-chips d-flex align-items-center" style="gap:8px;"></div>
    </div>
  `).appendTo($root);

	const $search = $toolbar.find('input[type="text"]');
	const $chips = $toolbar.find(".grp-chips");
	const $list = $(`<div style="margin-top:14px;"></div>`).appendTo($root);

	let currentGroup = "__all";
	let allItems = [];
	let allGroups = [];

	// === FILTER LOGIC (defined once) ===
	function applyFilters() {
		const searchTerm = ($search.val() || "").toLowerCase().trim();

		if (searchTerm) {
			// Search mode: apply BOTH group and text filter
			$list.find(".dash-card").each(function () {
				const $card = $(this);
				const cardText = $card.attr("data-search-text") || "";
				const cardGroup = $card.attr("data-group") || "";

				// Check if card matches search AND belongs to current group (or All)
				const matchesSearch = cardText.includes(searchTerm);
				const isInCurrentGroup = currentGroup === "__all" || cardGroup === currentGroup;

				const shouldShow = matchesSearch && isInCurrentGroup;

				if (shouldShow) {
					$card.addClass("is-visible").css("display", "block");
				} else {
					$card.removeClass("is-visible").css("display", "none");
				}
			});

			// Hide sections with no visible cards
			$list.find(".kpi-section").each(function () {
				const $section = $(this);
				const hasVisible = $section.find(".dash-card.is-visible").length > 0;
				$section.css("display", hasVisible ? "block" : "none");
			});
		} else {
			// Group mode: show sections AND their cards
			if (currentGroup === "__all") {
				$list
					.find(".kpi-section, .dash-card")
					.css("display", "block")
					.addClass("is-visible");
			} else {
				// Hide all sections and cards first
				$list
					.find(".kpi-section, .dash-card")
					.css("display", "none")
					.removeClass("is-visible");

				// Show only the active section and its cards
				$list.find(`.kpi-section[data-group="${currentGroup}"]`).css("display", "block");
				$list
					.find(`.dash-card[data-group="${currentGroup}"]`)
					.css("display", "block")
					.addClass("is-visible");
			}
		}
	}

	// === EVENT HANDLERS (bound once) ===
	$search.on("input", applyFilters);
	// Fallback for backspace/delete in case 'input' misses it
	$search.on("keydown", function (e) {
		if (e.key === "Backspace" || e.key === "Delete") {
			setTimeout(applyFilters, 10); // slight delay to let value update
		}
	});

	$chips.on("click", ".grp-filter", function () {
		const grp = $(this).data("group");
		currentGroup = grp;

		$chips.find(".grp-filter").removeClass("active");
		$(this).addClass("active");

		if (grp === "__all") {
			$search.val("");
		}

		applyFilters();
	});

	// === DATA FETCHING ===
	async function fetch_groups() {
		const rows = await frappe.db.get_list("Analytix Dashboard", {
			fields: ["kpi_group"],
			filters: { is_enabled: 1 },
			distinct: true,
			limit: 200,
		});
		return rows
			.map((r) => r.kpi_group)
			.filter(Boolean)
			.map((g) => g.trim())
			.filter(Boolean)
			.sort();
	}

	async function fetch_items() {
		return await frappe.db.get_list("Analytix Dashboard", {
			fields: [
				"name",
				"title",
				"dashboard",
				"kpi_group",
				"description",
				"icon",
				"sort_order",
				"is_enabled",
				"route_override",
			],
			filters: { is_enabled: 1 },
			order_by: "sort_order asc, title asc",
			limit: 1000,
		});
	}

	function toRoute(it) {
		if (it.route_override) return it.route_override;
		return `/app/dashboard-view/${encodeURIComponent(it.dashboard)}`;
	}

	function card(it) {
		const icon = it.icon || "layout-grid";
		const title = it.title || it.dashboard;
		const desc = it.description || "";
		const route = toRoute(it);
		const kpiGroup = (it.kpi_group || "").trim();

		// Combine all searchable text
		const searchText = [title, desc, kpiGroup].join(" ").toLowerCase();

		return `
      <div class="card dash-card" 
          data-group="${frappe.utils.escape_html(kpiGroup)}" 
          data-search-text="${frappe.utils.escape_html(searchText)}">
        <div class="card-body">
          <div class="flex justify-between items-center">
            <div>
              <div class="flex items-center gap-2">
                <i class="uil uil-${icon}"></i>
                <a class="h5" href="${route}">${frappe.utils.escape_html(title)}</a>
              </div>
              ${
					desc
						? `<div class="text-muted small" style="margin-top:2px;">${frappe.utils.escape_html(
								desc
						  )}</div>`
						: ``
				}
            </div>
            <div><a class="btn btn-default btn-sm" href="${route}">Open</a></div>
          </div>
        </div>
      </div>`;
	}

	async function render(groups, items) {
		allGroups = groups;
		allItems = items;

		$chips.empty();
		$list.empty();

		// Chips
		$chips.append(
			`<button class="btn btn-default btn-sm grp-filter ${
				currentGroup === "__all" ? "active" : ""
			}" data-group="__all">All</button>`
		);
		groups.forEach((g) => {
			$chips.append(`
        <button class="btn btn-default btn-sm grp-filter ${
			currentGroup === g ? "active" : ""
		}" data-group="${frappe.utils.escape_html(g)}">
          ${frappe.utils.escape_html(g)}
        </button>
      `);
		});

		// Build sections
		const by = {};
		items.forEach((it) => {
			const g = (it.kpi_group || "").trim();
			if (g) {
				(by[g] ||= []).push(it);
			}
		});

		groups.forEach((g) => {
			const arr = by[g];
			if (!arr?.length) return;
			$list.append(`
        <div class="kpi-section" data-group="${frappe.utils.escape_html(
			g
		)}" style="margin-top:12px;">
          <div class="h6 text-muted" style="margin-bottom:6px;">${frappe.utils.escape_html(
				g
			)}</div>
          <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:12px;">
            ${arr.map(card).join("")}
          </div>
        </div>
      `);
		});

		applyFilters(); // initial render
	}

	async function refresh() {
		const [groups, items] = await Promise.all([fetch_groups(), fetch_items()]);
		await render(groups, items);
	}

	await refresh();
};
