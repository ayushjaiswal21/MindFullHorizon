/* MindFull Horizon shell: theme, menu, progress bar, back to top, consent, toasts, analytics hook.
   No Jinja tags here. Server values arrive through data-* attributes on <body> and a JSON script block (#flash-data).
   Public API: window.MFH = { toast, consent, track, debounce }. */
(function () {
  'use strict';

  var root = document.documentElement;
  var MFH = window.MFH = window.MFH || {};
  var reduceMotion = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  function store(op, key, value) {
    try {
      if (op === 'get') return localStorage.getItem(key);
      if (op === 'set') localStorage.setItem(key, value);
      if (op === 'del') localStorage.removeItem(key);
    } catch (e) { /* private mode or blocked storage */ }
    return null;
  }
  function session(op, key, value) {
    try {
      if (op === 'get') return sessionStorage.getItem(key);
      if (op === 'set') sessionStorage.setItem(key, value);
      if (op === 'del') sessionStorage.removeItem(key);
    } catch (e) { /* ignore */ }
    return null;
  }
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  MFH.debounce = function (fn, ms) {
    var t;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms == null ? 200 : ms);
    };
  };

  /* ---------- Theme ---------- */
  var themeBtn = $('[data-theme-toggle]');
  function currentTheme() { return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'; }
  function paintThemeButton() {
    if (themeBtn) themeBtn.setAttribute('aria-label', currentTheme() === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  }
  paintThemeButton();
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var next = currentTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      store('set', 'mfh_theme', next);
      paintThemeButton();
      MFH.track('theme_toggle');
    });
  }
  if (window.matchMedia) {
    var mq = matchMedia('(prefers-color-scheme: dark)');
    var onSystem = function (e) {
      var saved = store('get', 'mfh_theme');
      if (saved !== 'light' && saved !== 'dark') { root.setAttribute('data-theme', e.matches ? 'dark' : 'light'); paintThemeButton(); }
    };
    if (mq.addEventListener) mq.addEventListener('change', onSystem);
  }

  /* ---------- Menu and dropdown groups ---------- */
  var menu = $('[data-site-menu]');
  var menuBtn = $('[data-menu-toggle]');
  var desktop = window.matchMedia ? matchMedia('(min-width: 72rem)') : { matches: false };

  function setMenu(open, returnFocus) {
    if (!menu || !menuBtn) return;
    menu.classList.toggle('is-open', open);
    menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    menuBtn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    if (open) {
      var first = $('a, button, input', menu);
      if (first && !desktop.matches) first.focus();
    } else if (returnFocus) {
      menuBtn.focus();
    }
  }
  if (menu && menuBtn) {
    setMenu(false, false);
    menuBtn.addEventListener('click', function () { setMenu(menuBtn.getAttribute('aria-expanded') !== 'true', true); });
    menu.addEventListener('click', function (e) {
      if (e.target.closest('a') && !desktop.matches) setMenu(false, false);
    });
    var onWide = function (e) { if (e.matches) setMenu(false, false); };
    if (desktop.addEventListener) desktop.addEventListener('change', onWide);
  }

  function closeGroups(except, returnFocus) {
    $$('[data-menu-group] > button[aria-expanded="true"]').forEach(function (b) {
      if (except && b.parentNode === except) return;
      b.setAttribute('aria-expanded', 'false');
      if (returnFocus) b.focus();
    });
  }
  $$('[data-menu-group] > button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') !== 'true';
      closeGroups(btn.parentNode, false);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });
  $$('[data-menu-group]').forEach(function (g) {
    g.addEventListener('focusout', function (e) {
      if (!e.relatedTarget || !g.contains(e.relatedTarget)) {
        var b = $('button', g);
        if (b) b.setAttribute('aria-expanded', 'false');
      }
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('[data-menu-group]')) closeGroups(null, false);
    if (menu && menu.classList.contains('is-open') && !desktop.matches && !e.target.closest('.site-header')) setMenu(false, false);
  });

  /* ---------- Scroll progress and back to top ---------- */
  var bar = $('#mfh-progress');
  var toTop = $('#back-to-top');
  var ticking = false;
  function frame() {
    ticking = false;
    var y = window.pageYOffset || root.scrollTop;
    if (bar && !reduceMotion) {
      var max = root.scrollHeight - window.innerHeight;
      bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, y / max) : 0) + ')';
    }
    if (toTop) toTop.classList.toggle('is-visible', y > 600);
  }
  function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', MFH.debounce(onScroll, 100), { passive: true });
  frame();
  if (toTop) {
    toTop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
      var main = $('#main-content');
      if (main) main.focus({ preventScroll: true });
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (menu && menu.classList.contains('is-open') && !desktop.matches) { setMenu(false, true); return; }
    if ($('[data-menu-group] > button[aria-expanded="true"]')) { closeGroups(null, true); return; }
    if (banner && !banner.hidden && openedByUser) { hideBanner(); }
  });

  /* ---------- Toasts ---------- */
  var region = $('#toast-region');
  var iconsUrl = document.body.getAttribute('data-icons') || '/static/img/icons.svg';
  var TOAST_ICON = { success: 'check', error: 'alert', warning: 'alert', info: 'info' };
  var SVGNS = 'http://www.w3.org/2000/svg';
  function svgIcon(name, size) {
    var s = document.createElementNS(SVGNS, 'svg');
    s.setAttribute('class', 'icon'); s.setAttribute('width', size); s.setAttribute('height', size);
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '1.75'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round');
    s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false');
    var u = document.createElementNS(SVGNS, 'use');
    u.setAttribute('href', iconsUrl + '#icon-' + name);
    s.appendChild(u);
    return s;
  }
  MFH.toast = function (message, type) {
    if (!region || !message) return null;
    type = TOAST_ICON[type] ? type : 'info';
    var existing = $$('.toast', region);
    for (var i = 0; i < existing.length; i++) {
      if (existing[i].getAttribute('data-msg') === String(message)) return existing[i];
    }
    if (existing.length >= 4) existing[0].remove();
    var el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.setAttribute('data-msg', String(message));
    var msg = document.createElement('div');
    msg.className = 'toast-msg';
    msg.textContent = String(message);
    var close = document.createElement('button');
    close.type = 'button'; close.className = 'toast-close'; close.setAttribute('aria-label', 'Dismiss message');
    close.appendChild(svgIcon('x', 16));
    el.appendChild(svgIcon(TOAST_ICON[type], 20));
    el.appendChild(msg);
    el.appendChild(close);
    region.appendChild(el);

    var timer = null, delay = type === 'error' ? 10000 : 6000;
    function dismiss() {
      clearTimeout(timer);
      if (!el.parentNode) return;
      el.classList.add('is-leaving');
      setTimeout(function () { if (el.parentNode) el.remove(); }, reduceMotion ? 0 : 200);
    }
    function arm() { clearTimeout(timer); timer = setTimeout(dismiss, delay); }
    close.addEventListener('click', dismiss);
    el.addEventListener('mouseenter', function () { clearTimeout(timer); });
    el.addEventListener('mouseleave', arm);
    el.addEventListener('focusin', function () { clearTimeout(timer); });
    el.addEventListener('focusout', arm);
    arm();
    return el;
  };
  var flash = $('#flash-data');
  if (flash) {
    try {
      JSON.parse(flash.textContent).forEach(function (pair) {
        var cat = pair[0];
        MFH.toast(pair[1], cat === 'success' ? 'success' : (cat === 'error' || cat === 'danger') ? 'error' : cat === 'warning' ? 'warning' : 'info');
      });
    } catch (e) { /* malformed flash data is ignored */ }
  }

  /* ---------- Consent ---------- */
  var banner = $('#consent-banner');
  var version = document.body.getAttribute('data-consent-version') || '2026-11';
  var KEY = 'mfh_consent';
  var YEAR = 31536000;
  var openedByUser = false, opener = null;

  function readCookie() {
    var m = document.cookie.match(/(?:^|;\s*)mfh_consent=([^;]*)/);
    if (!m) return null;
    var parts = decodeURIComponent(m[1]).split('.');
    return parts.length === 2 ? { v: parts[1], analytics: parts[0] === 'analytics' } : null;
  }
  function readChoice() {
    var raw = store('get', KEY), c = null;
    if (raw) { try { c = JSON.parse(raw); } catch (e) { c = null; } }
    if (!c || c.v !== version) c = readCookie();
    return c && c.v === version ? c : null;
  }
  function writeChoice(analytics) {
    store('set', KEY, JSON.stringify({ v: version, analytics: analytics, ts: new Date().toISOString() }));
    var secure = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = KEY + '=' + encodeURIComponent((analytics ? 'analytics' : 'essential') + '.' + version) +
      '; Max-Age=' + YEAR + '; Path=/; SameSite=Lax' + secure;
  }
  function showBanner(byUser) {
    if (!banner) return;
    openedByUser = !!byUser;
    banner.hidden = false;
    root.setAttribute('data-banner', 'open');
    if (byUser) { var h = $('#consent-title'); if (h) h.focus(); }
  }
  function hideBanner() {
    if (!banner) return;
    banner.hidden = true;
    root.removeAttribute('data-banner');
    if (openedByUser && opener && document.contains(opener)) opener.focus();
    openedByUser = false;
  }

  var initial = readChoice();
  MFH.consent = {
    analytics: !!(initial && initial.analytics),
    version: version,
    decided: !!initial,
    set: function (analytics) {
      analytics = !!analytics;
      writeChoice(analytics);
      this.analytics = analytics;
      this.decided = true;
      if (analytics) { captureUtm(); sendPageView(); } else { session('del', 'mfh_utm'); }
      hideBanner();
      document.dispatchEvent(new CustomEvent('mfh:consent', { detail: { analytics: analytics } }));
    },
    open: function () { opener = document.activeElement; showBanner(true); }
  };
  if (banner) {
    $$('[data-consent]', banner).forEach(function (b) {
      b.addEventListener('click', function () { MFH.consent.set(b.getAttribute('data-consent') === 'analytics'); });
    });
    $$('[data-consent-open]').forEach(function (b) {
      b.addEventListener('click', function () { MFH.consent.open(); });
    });
    if (!initial) showBanner(false);
  }

  /* ---------- Analytics (only after opt-in) ---------- */
  var EVENTS = ['page_view', 'signup_start', 'signup_complete', 'login', 'assessment_start', 'assessment_complete',
    'chat_open', 'contact_submit', 'blog_read', 'cta_click', 'theme_toggle'];
  var UTM = ['utm_source', 'utm_medium', 'utm_campaign'];

  function captureUtm() {
    if (!MFH.consent.analytics) return;
    var q = new URLSearchParams(location.search), found = {}, any = false;
    UTM.forEach(function (k) { var v = q.get(k); if (v) { found[k] = v.slice(0, 100); any = true; } });
    if (any) session('set', 'mfh_utm', JSON.stringify(found));
  }
  function savedUtm() {
    var raw = session('get', 'mfh_utm');
    if (!raw) return {};
    try { return JSON.parse(raw) || {}; } catch (e) { return {}; }
  }
  // props is accepted for call-site symmetry; the server stores only name, path and the utm fields, so nothing else is sent.
  MFH.track = function (name, props) {
    try {
      if (!MFH.consent || !MFH.consent.analytics || EVENTS.indexOf(name) === -1) return;
      var body = { name: name, path: (props && typeof props.path === 'string' ? props.path : location.pathname).slice(0, 200) };
      var u = savedUtm();
      UTM.forEach(function (k) { if (u[k]) body[k] = u[k]; });
      var headers = { 'Content-Type': 'application/json', 'X-Analytics-Consent': 'granted' };
      var csrf = $('meta[name="csrf-token"]');
      if (csrf) headers['X-CSRFToken'] = csrf.getAttribute('content');
      fetch(document.body.getAttribute('data-event-url') || '/api/event', {
        method: 'POST', headers: headers, body: JSON.stringify(body), keepalive: true, credentials: 'same-origin'
      }).catch(function () { /* analytics must never affect the page */ });
    } catch (e) { /* ignore */ }
  };
  var viewSent = false;
  function sendPageView() {
    if (viewSent || !MFH.consent.analytics) return;
    viewSent = true;
    MFH.track('page_view');
  }
  captureUtm();
  sendPageView();

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-track]') : null;
    if (t) MFH.track(t.getAttribute('data-track'));
  });
})();
