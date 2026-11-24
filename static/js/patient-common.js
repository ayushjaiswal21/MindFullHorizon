/* Shared helpers for the patient pages. No Jinja here; server values come from data-* attributes or JSON blocks.
   Uses window.MFH (toast, confirm, debounce) from the shell when it is there. */
(function () {
  'use strict';

  var meta = document.querySelector('meta[name="csrf-token"]');
  var SVG_NS = 'http://www.w3.org/2000/svg';

  function statusLine() {
    var el = document.getElementById('pt-status');
    if (!el) {
      el = document.createElement('p');
      el.id = 'pt-status';
      el.className = 'alert alert-info';
      el.setAttribute('role', 'status');
      el.setAttribute('aria-live', 'polite');
      el.hidden = true;
      var host = document.querySelector('main') || document.body;
      host.insertBefore(el, host.firstChild);
    }
    return el;
  }

  var PT = {
    csrf: function () { return meta ? meta.getAttribute('content') : ''; },

    // type: info | success | error
    toast: function (message, type) {
      if (window.MFH && typeof window.MFH.toast === 'function') {
        window.MFH.toast(message, type || 'info');
        return;
      }
      var el = statusLine();
      el.className = 'alert alert-' + (type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info');
      el.textContent = message;
      el.hidden = false;
    },

    // Resolves true only when the person confirms. Without the shell dialog it refuses, so nothing is deleted by accident.
    ask: function (opts) {
      if (window.MFH && typeof window.MFH.confirm === 'function') return window.MFH.confirm(opts);
      PT.toast('The confirmation dialog did not load. Reload the page and try again.', 'error');
      return Promise.resolve(false);
    },

    debounce: function (fn, wait) {
      if (window.MFH && typeof window.MFH.debounce === 'function') return window.MFH.debounce(fn, wait);
      var t = null;
      return function () {
        var args = arguments, self = this;
        clearTimeout(t);
        t = setTimeout(function () { fn.apply(self, args); }, wait);
      };
    },

    // Resolves {ok, status, data}; data is null when the body is not JSON.
    api: function (url, opts) {
      opts = opts || {};
      var headers = { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': PT.csrf() };
      if (opts.json !== undefined) headers['Content-Type'] = 'application/json';
      return fetch(url, {
        method: opts.method || 'GET',
        credentials: 'same-origin',
        headers: headers,
        body: opts.json !== undefined ? JSON.stringify(opts.json) : undefined
      }).then(function (res) {
        return res.json().catch(function () { return null; }).then(function (data) {
          return { ok: res.ok, status: res.status, data: data };
        });
      });
    },

    svg: function (name, attrs) {
      var el = document.createElementNS(SVG_NS, name);
      Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
      return el;
    },

    /* Line chart in inline SVG.
       opts: {labels:[], series:[{values:[], cls:'a'|'b'}], min, max, ticks, height, compact, label} */
    lineChart: function (host, opts) {
      var W = 640, H = opts.height || 220, compact = !!opts.compact;
      var m = compact ? { l: 6, r: 6, t: 6, b: 6 } : { l: 30, r: 10, t: 10, b: 24 };
      var iw = W - m.l - m.r, ih = H - m.t - m.b;
      var n = opts.labels.length;
      var svg = PT.svg('svg', { viewBox: '0 0 ' + W + ' ' + H, 'class': 'chart', role: 'img', 'aria-label': opts.label || 'Chart' });
      function x(i) { return m.l + (n < 2 ? iw / 2 : (iw * i) / (n - 1)); }
      function y(v) { return m.t + ih - ((v - opts.min) / (opts.max - opts.min)) * ih; }
      if (!compact) {
        var ticks = opts.ticks || 4;
        for (var t = 0; t <= ticks; t++) {
          var v = opts.min + ((opts.max - opts.min) * t) / ticks;
          svg.appendChild(PT.svg('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), 'class': t === 0 ? 'axis' : 'grid' }));
          var tx = PT.svg('text', { x: m.l - 6, y: y(v) + 4, 'text-anchor': 'end' });
          tx.textContent = String(Math.round(v * 10) / 10);
          svg.appendChild(tx);
        }
        var marks = n < 3 ? [0, n - 1] : [0, Math.floor((n - 1) / 2), n - 1];
        marks.forEach(function (i, k) {
          if (i < 0) return;
          var lx = PT.svg('text', { x: x(i), y: H - 6, 'text-anchor': k === 0 ? 'start' : k === marks.length - 1 ? 'end' : 'middle' });
          lx.textContent = opts.labels[i];
          svg.appendChild(lx);
        });
      }
      opts.series.forEach(function (s) {
        var d = '', pen = false, pts = [];
        s.values.forEach(function (val, i) {
          if (val === null || val === undefined) { pen = false; return; }
          d += (pen ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(val).toFixed(1) + ' ';
          pen = true;
          pts.push([x(i), y(val)]);
        });
        if (d) svg.appendChild(PT.svg('path', { d: d, 'class': 'line-' + s.cls }));
        if (!compact || pts.length === 1) {
          pts.forEach(function (p) { svg.appendChild(PT.svg('circle', { cx: p[0], cy: p[1], r: 3, 'class': 'dot-' + s.cls })); });
        }
      });
      host.textContent = '';
      host.appendChild(svg);
    }
  };

  window.PT = PT;
})();
