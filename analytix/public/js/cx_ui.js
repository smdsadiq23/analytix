// CX UI helpers (public)
// Safe global namespace
window.CX = window.CX || {};

(function (CX) {
  /**
   * waitFor: polls for a DOM node and runs a callback when it's ready.
   * @param {Function} checkFn  -> should return a jQuery object or null
   * @param {Function} onReady  -> called with the jQuery object
   * @param {Object}   opts     -> { timeoutMs, intervalMs }
   */
  CX.waitFor = function waitFor(checkFn, onReady, { timeoutMs = 3000, intervalMs = 80 } = {}) {
    const start = Date.now();
    (function poll() {
      try {
        const $node = checkFn();
        if ($node && $node.length) return onReady($node);
      } catch (_) {}
      if (Date.now() - start >= timeoutMs) {
        return setTimeout(() => CX.waitFor(checkFn, onReady, { timeoutMs, intervalMs }), 250);
      }
      setTimeout(poll, intervalMs);
    })();
  };

  /**
   * mountBreadcrumb: inserts a breadcrumb bar BEFORE the page header.
   * Works on Query Reports and Custom Pages.
   *
   * @param {Object}  opts
   * @param {HTMLElement} opts.wrapper      -> the page wrapper you get in on_page_load / onload
   * @param {Array<{label:string, href?:string}>} opts.trail -> breadcrumb trail (left to right)
   * @param {string}  [opts.className]      -> extra class on the bar
   */
  CX.mountBreadcrumb = function mountBreadcrumb({ wrapper, trail, className = "" }) {
    if (!wrapper || !trail || !trail.length) return;

    CX.waitFor(
      () => $(wrapper).find(".page-head").first(),
      ($head) => {
        if (!$head.length) return;
        if ($head.prev(".cx-breadcrumb-bar").length) return; // no dupes

        // Build breadcrumb HTML
        const items = trail.map((t, i) => {
          const isLast = i === trail.length - 1;
          const text = frappe.utils.escape_html(t.label || "");
          if (!isLast && t.href) {
            return `<a href="${t.href}" class="cx-bc-link">${text}</a><span class="cx-bc-sep">›</span>`;
          }
          if (!isLast) {
            return `<span class="cx-bc-text">${text}</span><span class="cx-bc-sep">›</span>`;
          }
          // last item
          return `<span class="cx-bc-last">${text}</span>`;
        }).join("");

        const $bar = $(`
          <div class="cx-breadcrumb-bar ${className}">
            ${items}
          </div>
        `);

        $bar.insertBefore($head);

        // Keep it if header re-renders
        if (!window.__cxBreadcrumbObserver) {
          const host = $head.parent()[0];
          if (host) {
            const mo = new MutationObserver(() => {
              if (!$head.prev(".cx-breadcrumb-bar").length) {
                $bar.insertBefore($head);
              }
            });
            mo.observe(host, { childList: true });
            window.__cxBreadcrumbObserver = mo;
          }
        }
      }
    );
  };
})(window.CX);
