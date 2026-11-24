/* Shared helpers for the wellness pages. No Jinja; uses window.MFH (toast, confirm, debounce) when the shell has it. */
(function () {
  'use strict';
  if (window.WL) return;
  var WL = (window.WL = {});

  WL.csrf = function () {
    var m = document.querySelector('meta[name="csrf-token"]');
    if (m && m.content) return m.content;
    var i = document.querySelector('input[name="csrf_token"]');
    return i ? i.value : '';
  };

  function statusLine() {
    var node = document.getElementById('wl-status');
    if (!node) {
      node = document.createElement('p');
      node.id = 'wl-status';
      node.className = 'alert alert-info';
      node.setAttribute('role', 'status');
      node.hidden = true;
      var host = document.querySelector('main') || document.body;
      host.insertBefore(node, host.firstChild);
    }
    return node;
  }

  /* type: info | success | error */
  WL.toast = function (message, type) {
    if (window.MFH && typeof MFH.toast === 'function') { MFH.toast(message, type || 'info'); return; }
    var node = statusLine();
    node.className = 'alert alert-' + (type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info');
    node.textContent = message;
    node.hidden = false;
  };

  /* Resolves true only when the person confirms; without the shell dialog it refuses, so nothing is deleted by accident. */
  WL.ask = function (opts) {
    if (window.MFH && typeof MFH.confirm === 'function') return MFH.confirm(opts);
    WL.toast('The confirmation dialog did not load. Reload the page and try again.', 'error');
    return Promise.resolve(false);
  };

  WL.debounce = function (fn, wait) {
    if (window.MFH && typeof MFH.debounce === 'function') return MFH.debounce(fn, wait);
    var t = null;
    return function () {
      var args = arguments, self = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(self, args); }, wait == null ? 200 : wait);
    };
  };

  /* Resolves {ok, status, data}; data is null when the body is not JSON. */
  WL.api = function (url, opts) {
    opts = opts || {};
    var headers = { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': WL.csrf() };
    if (opts.json !== undefined) headers['Content-Type'] = 'application/json';
    return fetch(url, {
      method: opts.method || 'GET',
      credentials: 'same-origin',
      headers: headers,
      body: opts.json !== undefined ? JSON.stringify(opts.json) : (opts.body || undefined)
    }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  };

  /* data-validate forms run required/length checks (components.js). This adds min/max for number inputs, which
     the browser skips because components.js sets novalidate. */
  WL.guardRanges = function (form) {
    if (!form) return;
    form.addEventListener('submit', function (e) {
      var bad = null;
      form.querySelectorAll('input[type="number"]').forEach(function (f) {
        var err = document.getElementById(f.id + '-error');
        var msg = '';
        if (f.value !== '') {
          var v = Number(f.value), min = f.min === '' ? null : Number(f.min), max = f.max === '' ? null : Number(f.max);
          if (isNaN(v) || (min !== null && v < min) || (max !== null && v > max)) {
            msg = 'Enter a number from ' + f.min + ' to ' + f.max + '.';
          }
        }
        if (msg) {
          if (!bad) bad = f;
          f.setAttribute('aria-invalid', 'true');
          if (err) { err.textContent = msg; err.hidden = false; err.dataset.range = '1'; }
        } else if (err && err.dataset.range === '1') {
          f.removeAttribute('aria-invalid');
          err.textContent = '';
          err.hidden = true;
        }
      });
      if (bad) { e.preventDefault(); bad.focus(); }
    });
  };

  /* Show a server error text next to a field without a page reload. */
  WL.fieldError = function (field, message) {
    var err = document.getElementById(field.id + '-error');
    if (!err) return;
    err.textContent = message || '';
    err.hidden = !message;
    if (message) field.setAttribute('aria-invalid', 'true'); else field.removeAttribute('aria-invalid');
  };

  WL.el = function (tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
})();
