// KPI Hub — lists Dashboards from the "Analytix Dashboard" registry, grouped by kpi_group
frappe.pages['kpi-hub'].on_page_load = async function (wrapper) {
  const page = frappe.ui.make_app_page({ parent: wrapper, title: 'KPI Hub', single_column: true });
  const $root = $(wrapper).find('.layout-main-section');

  // toolbar (Frappe default buttons + spacing)
  const $toolbar = $(`
    <div class="d-flex align-items-center" style="margin-top:12px; gap:8px;">
      <input type="text" class="form-control" placeholder="Search dashboards..." style="max-width:280px;">
      <div class="grp-chips d-flex align-items-center" style="gap:8px;"></div>
      <button class="btn btn-default btn-sm" data-action="refresh">Refresh</button>
    </div>
  `).appendTo($root);

  const $search = $toolbar.find('input[type="text"]');
  const $chips  = $toolbar.find('.grp-chips');
  const $list   = $(`<div style="margin-top:14px;"></div>`).appendTo($root);

  async function fetch_groups() {
    const rows = await frappe.db.get_list('Analytix Dashboard', {
      fields: ['kpi_group'],
      filters: { is_enabled: 1 },
      distinct: true,
      limit: 200
    });
    return rows.map(r => r.kpi_group).filter(Boolean).sort();
  }

  async function fetch_items() {
    return await frappe.db.get_list('Analytix Dashboard', {
      fields: ['name','title','dashboard','kpi_group','description','icon','sort_order','is_enabled','route_override'],
      filters: { is_enabled: 1 },
      order_by: 'sort_order asc, title asc',
      limit: 1000
    });
  }

  // Prefer dashboard viewer route; fall back to override if provided
  function toRoute(it) {
    if (it.route_override) return it.route_override;
    const encoded = encodeURIComponent(it.dashboard);
    return `/app/dashboard-view/${encoded}`;
    // or: return `/app/analytics/${encoded}`;
    // or: return `/app/dashboard/${encoded}?view=dashboard`;
  }

  function card(it) {
    const icon  = it.icon || 'layout-grid';
    const title = it.title || it.dashboard;
    const desc  = it.description ? frappe.utils.escape_html(it.description) : '';
    const route = toRoute(it);
    return `
      <div class="card dash-card" data-group="${frappe.utils.escape_html(it.kpi_group)}">
        <div class="card-body">
          <div class="flex justify-between items-center">
            <div>
              <div class="flex items-center gap-2">
                <i class="uil uil-${icon}"></i>
                <a class="h5" href="${route}">${frappe.utils.escape_html(title)}</a>
              </div>
              ${desc ? `<div class="text-muted small" style="margin-top:2px;">${desc}</div>` : ``}
            </div>
            <div><a class="btn btn-default btn-sm" href="${route}">Open</a></div>
          </div>
        </div>
      </div>`;
  }

  function render(groups, items) {
    $chips.empty(); 
    $list.empty();

    // chips (standalone buttons with spacing)
    $chips.append(`<button class="btn btn-default btn-sm grp-filter active" data-group="__all">All</button>`);
    groups.forEach(g => {
      $chips.append(
        `<button class="btn btn-default btn-sm grp-filter" data-group="${frappe.utils.escape_html(g)}">${frappe.utils.escape_html(g)}</button>`
      );
    });

    // group items
    const by = {}; 
    groups.forEach(g => (by[g] = []));
    items.forEach(it => (by[it.kpi_group] ||= []).push(it));

    // sections
    groups.forEach(g => {
      const arr = by[g]; 
      if (!arr || !arr.length) return;
      $list.append(`
        <div class="kpi-section" data-group="${frappe.utils.escape_html(g)}" style="margin-top:12px;">
          <div class="h6 text-muted" style="margin-bottom:6px;">${frappe.utils.escape_html(g)}</div>
          <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:12px;">
            ${arr.map(card).join('')}
          </div>
        </div>
      `);
    });

    // search + chip filter
    const applyText = term => {
      const t = (term || '').toLowerCase();
      $list.find('.dash-card').each(function () {
        $(this).toggle($(this).text().toLowerCase().includes(t));
      });
      hideEmptySections();
    };

    const applyGroup = grp => {
      if (grp === '__all') {
        $list.find('.dash-card,.kpi-section').show();
      } else {
        $list.find('.dash-card').hide().filter(`[data-group="${grp}"]`).show();
        hideEmptySections();
      }
    };

    function hideEmptySections() {
      $list.find('.kpi-section').each(function () {
        $(this).toggle($(this).find('.dash-card:visible').length > 0);
      });
    }

    $search.off('input').on('input', () => applyText($search.val()));
    $chips.off('click').on('click', '.grp-filter', function () {
      $chips.find('.grp-filter').removeClass('active');
      $(this).addClass('active');
      applyGroup($(this).data('group'));
    });
  }

  async function refresh() {
    const [groups, items] = await Promise.all([fetch_groups(), fetch_items()]);
    render(groups, items);
  }

  $toolbar.on('click', '[data-action="refresh"]', refresh);
  await refresh();
};
