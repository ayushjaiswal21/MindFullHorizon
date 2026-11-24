/* Shared helpers for the clinical screens (admin and prescribing). Page logic lives in the per-screen files.
   Adds to window.MFH: api, newKey, h, icon, cfg, clear, say, busy, fill, qs, ist, istDate, istTime, initTimes,
   badge, availBadge, statusBadge, emptyState, table, pager.
   Everything user-visible is built with textContent, never with markup strings. */
(function () {
  'use strict';
  var MFH = (window.MFH = window.MFH || {});
  var SVGNS = 'http://www.w3.org/2000/svg';
  var GENERIC = 'Something went wrong. Try again. If it keeps happening, contact your administrator.';
  var NETWORK = 'Could not reach the server. Check your connection and try again.';

  /* ---------- Small utilities ---------- */
  MFH.newKey = function () {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'k' + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
  };

  /* h('div', {class: 'x', text: 'hi', on: {click: fn}}, [children]) */
  MFH.h = function (tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === 'class') n.className = v;
      else if (k === 'text') n.textContent = v;
      else if (k === 'on') Object.keys(v).forEach(function (ev) { n.addEventListener(ev, v[ev]); });
      else n.setAttribute(k, v === true ? '' : v);
    });
    [].concat(kids == null ? [] : kids).forEach(function (c) {
      if (c == null || c === false) return;
      n.appendChild(c.nodeType ? c : document.createTextNode(String(c)));
    });
    return n;
  };

  MFH.icon = function (name, size) {
    var s = document.createElementNS(SVGNS, 'svg');
    s.setAttribute('class', 'icon');
    s.setAttribute('width', size || 18); s.setAttribute('height', size || 18);
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '1.75'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round');
    s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false');
    var u = document.createElementNS(SVGNS, 'use');
    u.setAttribute('href', (document.body.getAttribute('data-icons') || '') + '#icon-' + name);
    s.appendChild(u);
    return s;
  };

  MFH.cfg = function (id) {
    var n = document.getElementById(id || 'page-config');
    try { return n ? JSON.parse(n.textContent) : {}; } catch (e) { return {}; }
  };
  MFH.clear = function (n) { while (n && n.firstChild) n.removeChild(n.firstChild); return n; };
  MFH.say = function (n, msg) { if (n) n.textContent = msg || ''; };   // aria-live region
  MFH.busy = function (btn, on) {
    if (!btn) return;
    if (on) { btn.setAttribute('aria-busy', 'true'); btn.disabled = true; }
    else { btn.removeAttribute('aria-busy'); btn.disabled = false; }
  };
  /* fill('/provider/prescriptions/0', 12): replaces the 0 placeholder segment. */
  MFH.fill = function (tpl, id) { return String(tpl || '').replace(/\/0(?=\/|$|\?)/, '/' + encodeURIComponent(id)); };
  MFH.qs = function (obj) {
    var p = [];
    Object.keys(obj || {}).forEach(function (k) {
      if (obj[k] != null && obj[k] !== '') p.push(encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]));
    });
    return p.length ? '?' + p.join('&') : '';
  };

  /* ---------- API ----------
     MFH.api(method, url, body, {idem: key|true, signal}) resolves with the parsed JSON.
     It rejects with {status, error, message, fields, body}. idem: pass a key you created when the
     screen opened and send the SAME key on a retry; true makes a one-off key (only for calls that
     are never retried). Server text is shown as sent; exception text never reaches the page. */
  MFH.api = function (method, url, body, opts) {
    opts = opts || {};
    var headers = { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' };
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) headers['X-CSRFToken'] = meta.getAttribute('content');
    var init = { method: method, headers: headers, credentials: 'same-origin', signal: opts.signal };
    if (typeof FormData !== 'undefined' && body instanceof FormData) init.body = body;
    else if (body != null) { headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(body); }
    if (opts.idem) headers['Idempotency-Key'] = opts.idem === true ? MFH.newKey() : String(opts.idem);
    return fetch(url, init).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (data) {
        if (res.ok && (!data || data.success !== false)) return data || { success: true };
        throw { status: res.status, error: (data && data.error) || 'error', message: (data && data.message) || GENERIC,
                fields: (data && data.fields) || {}, body: data || {} };
      });
    }, function (err) {
      if (err && err.name === 'AbortError') throw { status: 0, error: 'aborted', aborted: true, message: '' };
      throw { status: 0, error: 'network', message: NETWORK };
    });
  };

  /* ---------- Times: the server sends UTC ISO strings, screens show Asia/Kolkata ---------- */
  function toDate(iso) {
    if (!iso) return null;
    var s = String(iso);
    if (s.indexOf('T') > -1 && !/(Z|[+-]\d\d:?\d\d)$/.test(s)) s += 'Z';
    var d = new Date(s.length === 10 ? s + 'T00:00:00Z' : s);
    return isNaN(d.getTime()) ? null : d;
  }
  function fmt(opts) {
    opts.timeZone = 'Asia/Kolkata';
    try { return new Intl.DateTimeFormat('en-GB', opts); } catch (e) { return null; }
  }
  var F_DT = fmt({ day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
  var F_D = fmt({ day: 'numeric', month: 'short', year: 'numeric' });
  var F_T = fmt({ hour: '2-digit', minute: '2-digit', hour12: false });
  function via(f) { return function (iso) { var d = toDate(iso); return d && f ? f.format(d) : (iso ? String(iso) : 'n/a'); }; }
  MFH.ist = via(F_DT);
  MFH.istDate = via(F_D);
  MFH.istTime = via(F_T);
  MFH.toDate = toDate;

  /* <time class="js-ist" datetime="..." data-ist="date|time|datetime"> gets its text in IST. */
  MFH.initTimes = function (root) {
    [].forEach.call((root || document).querySelectorAll('time[data-ist]'), function (t) {
      var iso = t.getAttribute('datetime'), kind = t.getAttribute('data-ist');
      if (!iso) return;
      t.textContent = (kind === 'date' ? MFH.istDate : kind === 'time' ? MFH.istTime : MFH.ist)(iso);
      t.title = 'Indian Standard Time';
    });
  };

  /* ---------- Badges (always text, never colour alone) ---------- */
  MFH.badge = function (text, kind, icon) {
    return MFH.h('span', { class: 'badge badge-' + (kind || 'neutral') }, [icon ? MFH.icon(icon, 14) : null, text]);
  };
  var AVAIL = {
    in_stock: ['In stock at your pharmacy desk', 'success', 'check'],
    low: ['Low stock', 'warning', 'alert'],
    out: ['Out of stock', 'danger', 'x']
  };
  MFH.availBadge = function (a, short) {
    var v = AVAIL[a];
    if (!v) return MFH.badge('Stock not known', 'neutral', 'info');
    return MFH.badge(short && a === 'in_stock' ? 'In stock' : v[0], v[1], v[2]);
  };
  var STATUS = {
    draft: ['Draft', 'neutral'], issued: ['Issued', 'info'], partially_dispensed: ['Partly collected', 'info'],
    dispensed: ['Collected', 'success'], cancelled: ['Cancelled', 'danger'], expired: ['Expired', 'warning'],
    legacy: ['Legacy', 'warning'], pending: ['Pending', 'warning'], verified: ['Verified', 'success'],
    rejected: ['Rejected', 'danger'], suspended: ['Suspended', 'danger']
  };
  MFH.statusBadge = function (s) { var v = STATUS[s] || [String(s || 'n/a'), 'neutral']; return MFH.badge(v[0], v[1]); };
  MFH.COLLECTION = { none: 'Not collected', partial: 'Partly collected', complete: 'Collected' };

  MFH.emptyState = function (title, text, icon) {
    return MFH.h('div', { class: 'empty-state' }, [
      MFH.icon(icon || 'info', 36),
      MFH.h('h3', { class: 'empty-state-title', text: title }),
      text ? MFH.h('p', { class: 'empty-state-text', text: text }) : null
    ]);
  };

  /* table(caption, cols, rows, empty): cols = [{label, render(row) -> Node|string, th: bool}] */
  MFH.table = function (caption, cols, rows, empty) {
    if (!rows || !rows.length) return empty || MFH.emptyState('Nothing to show');
    var thead = MFH.h('tr', {}, cols.map(function (c) { return MFH.h('th', { scope: 'col', text: c.label }); }));
    var body = rows.map(function (r) {
      return MFH.h('tr', {}, cols.map(function (c) {
        var v = c.render(r);
        return MFH.h(c.th ? 'th' : 'td', c.th ? { scope: 'row' } : {}, v == null || v === '' ? 'n/a' : v);
      }));
    });
    return MFH.h('div', { class: 'table-wrap' }, MFH.h('table', { class: 'table' }, [
      MFH.h('caption', { class: 'sr-only', text: caption }), MFH.h('thead', {}, thead), MFH.h('tbody', {}, body)]));
  };

  /* pager(meta, go): Previous and Next buttons plus a position line. */
  MFH.pager = function (meta, go) {
    if (!meta || (!meta.has_next && meta.page <= 1)) return null;
    var page = meta.page || 1;
    var text = 'Page ' + page + (meta.total != null ? ', ' + meta.total + ' in total' : '');
    return MFH.h('nav', { class: 'cl-pager', 'aria-label': 'Pages' }, [
      MFH.h('button', { type: 'button', class: 'btn btn-secondary btn-sm', disabled: page <= 1, text: 'Previous',
        on: { click: function () { go(page - 1); } } }),
      MFH.h('span', { class: 'muted', text: text }),
      MFH.h('button', { type: 'button', class: 'btn btn-secondary btn-sm', disabled: !meta.has_next, text: 'Next',
        on: { click: function () { go(page + 1); } } })
    ]);
  };

  /* A confirm that shows a clear busy state while the action runs. Resolves false when cancelled. */
  MFH.ask = function (o) { return MFH.confirm ? MFH.confirm(o) : Promise.resolve(false); };

  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-action="print"]');
    if (b) { e.preventDefault(); window.print(); }
  });
  document.addEventListener('DOMContentLoaded', function () { MFH.initTimes(document); });
})();
