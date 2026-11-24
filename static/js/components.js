/* MindFull Horizon UI components. No dependencies, no Jinja, safe to load with defer.
   Everything degrades without JS: forms still submit, accordion panels are native <details>.
   Public API on window.MFH: confirm, debounce (only if missing), copy, validateForm, formSuccess, initComponents. */
(function () {
  'use strict';

  var MFH = (window.MFH = window.MFH || {});
  if (MFH._componentsLoaded) return;
  MFH._componentsLoaded = true;

  function qs(sel, scope) { return (scope || document).querySelector(sel); }
  function qsa(sel, scope) { return Array.prototype.slice.call((scope || document).querySelectorAll(sel)); }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  if (typeof MFH.debounce !== 'function') {
    MFH.debounce = function (fn, wait) {
      var timer;
      return function () {
        var ctx = this, args = arguments;
        clearTimeout(timer);
        timer = setTimeout(function () { fn.apply(ctx, args); }, wait == null ? 200 : wait);
      };
    };
  }

  /* Polite live region for announcements that are not toasts. */
  var liveRegion;
  function announce(message) {
    if (!liveRegion) {
      liveRegion = el('div', 'mfh-visually-hidden');
      liveRegion.setAttribute('role', 'status');
      liveRegion.setAttribute('aria-live', 'polite');
      document.body.appendChild(liveRegion);
    }
    liveRegion.textContent = '';
    setTimeout(function () { liveRegion.textContent = message; }, 30);
  }

  /* ---------- Password show/hide ---------- */
  function setPasswordVisible(btn, input, show) {
    input.type = show ? 'text' : 'password';
    btn.setAttribute('aria-pressed', show ? 'true' : 'false');
    var label = qs('.mfh-toggle-label', btn);
    if (label) label.textContent = show ? 'Hide password' : 'Show password';
  }

  function initPasswordToggles(scope) {
    qsa('[data-toggle-password]', scope).forEach(function (btn) {
      if (btn._mfhToggle) return;
      btn._mfhToggle = true;
      var wrap = btn.closest('.password-field');
      var input = document.getElementById(btn.getAttribute('aria-controls') || '') || (wrap && qs('input', wrap));
      if (!input) return;
      btn.hidden = false; // hidden in markup so it is not a dead control without JS
      btn.addEventListener('click', function () {
        setPasswordVisible(btn, input, input.type === 'password');
      });
    });
  }

  /* ---------- Inline validation ---------- */
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function fieldLabel(field) {
    var label = field.id && qs('label[for="' + field.id + '"]');
    if (!label) return 'This field';
    var clone = label.cloneNode(true);
    qsa('.mfh-optional, .mfh-req, .mfh-visually-hidden', clone).forEach(function (n) { n.remove(); });
    return clone.textContent.replace(/\s+/g, ' ').trim() || 'This field';
  }

  function messageFor(field) {
    var d = field.dataset;
    var isCheck = field.type === 'checkbox' || field.type === 'radio';
    var value = isCheck ? '' : (field.type === 'password' ? field.value : field.value.trim());
    var required = field.required || field.hasAttribute('aria-required');
    if (required) {
      if (isCheck ? !field.checked : value === '') return d.msgRequired || (isCheck ? 'Tick this box to continue.' : fieldLabel(field) + ' is required.');
    }
    if (isCheck || value === '') return '';
    if ((field.type === 'email' || d.validate === 'email') && !EMAIL_RE.test(value)) {
      return d.msgEmail || 'Enter a valid email address, like name@example.com.';
    }
    var min = parseInt(field.getAttribute('minlength') || d.minlength || '', 10);
    if (min && value.length < min) return d.msgMinlength || 'Use at least ' + min + ' characters.';
    var max = parseInt(field.getAttribute('maxlength') || d.maxlength || '', 10);
    if (max && value.length > max) return d.msgMaxlength || 'Use at most ' + max + ' characters.';
    if (d.match) {
      var other = qs(d.match);
      if (other && other.value !== field.value) return d.msgMatch || 'The two entries do not match.';
    }
    return '';
  }

  function errorElement(field, create) {
    var id = (field.id || field.name) + '-error';
    var node = document.getElementById(id);
    if (!node && create) {
      node = el('p', 'error-text');
      node.id = id;
      node.hidden = true;
      var host = field.closest('.field') || field.closest('.check') || field.parentNode;
      host.appendChild(node);
    }
    return node;
  }

  function describedBy(field, id, on) {
    var tokens = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
    var i = tokens.indexOf(id);
    if (on && i < 0) tokens.push(id);
    if (!on && i >= 0) tokens.splice(i, 1);
    if (tokens.length) field.setAttribute('aria-describedby', tokens.join(' '));
    else field.removeAttribute('aria-describedby');
  }

  function setFieldError(field, message, assertive) {
    var node = errorElement(field, !!message);
    if (!node) return;
    if (message) {
      if (assertive) node.setAttribute('role', 'alert'); else node.removeAttribute('role');
      node.textContent = message;
      node.hidden = false;
      field.setAttribute('aria-invalid', 'true');
      describedBy(field, node.id, true);
    } else {
      node.textContent = '';
      node.removeAttribute('role');
      node.hidden = true;
      field.removeAttribute('aria-invalid');
      describedBy(field, node.id, false);
    }
  }

  function validatableFields(form) {
    return qsa('input, select, textarea', form).filter(function (f) {
      if (f.disabled || f.type === 'hidden' || f.type === 'submit' || f.type === 'button') return false;
      if (f.closest('[hidden], [aria-hidden="true"]')) return false;
      return true;
    });
  }

  /* Validates every field; the first invalid one gets focus and the only role="alert". */
  MFH.validateForm = function (form) {
    var firstInvalid = null;
    validatableFields(form).forEach(function (f) {
      var msg = messageFor(f);
      if (msg && !firstInvalid) { firstInvalid = f; setFieldError(f, msg, true); }
      else setFieldError(f, msg, false);
    });
    clearSuccess(form);
    if (firstInvalid) firstInvalid.focus();
    return !firstInvalid;
  };

  function successNote(form, create) {
    var node = qs('.success-text', form);
    if (!node && create) {
      node = el('p', 'success-text');
      node.setAttribute('role', 'status');
      form.insertBefore(node, form.firstChild);
    }
    return node;
  }
  function clearSuccess(form) {
    var node = successNote(form, false);
    if (node) { node.textContent = ''; node.hidden = true; }
  }
  MFH.formSuccess = function (form, message) {
    var node = successNote(form, true);
    node.textContent = message;
    node.hidden = false;
  };

  function initValidation(scope) {
    qsa('form[data-validate]', scope).forEach(function (form) {
      if (form._mfhValidate) return;
      form._mfhValidate = true;
      form.noValidate = true; // our messages replace the browser bubbles; without JS native validation still runs
      form.addEventListener('focusout', function (e) {
        var f = e.target;
        if (!f.matches || !f.matches('input, select, textarea') || f.type === 'hidden') return;
        // Quiet check on leaving a field: only show a message once the user typed something or the field already failed.
        if (f.value !== '' || f.getAttribute('aria-invalid') === 'true') setFieldError(f, messageFor(f), false);
      });
      form.addEventListener('input', function (e) {
        var f = e.target;
        if (f.getAttribute && f.getAttribute('aria-invalid') === 'true' && !messageFor(f)) setFieldError(f, '', false);
        if (f.id) {
          // keep a "match" partner in sync, e.g. confirm password
          qsa('[data-match="#' + f.id + '"]', form).forEach(function (p) {
            if (p.getAttribute('aria-invalid') === 'true') setFieldError(p, messageFor(p), false);
          });
        }
        clearSuccess(form);
      });
    });
  }

  /* ---------- Loading state and double-submit guard ---------- */
  function submitButtonsOf(form, submitter) {
    if (submitter && submitter.form === form) return [submitter];
    var first = qs('button[type="submit"], button:not([type]), input[type="submit"]', form);
    return first ? [first] : [];
  }

  function setLoading(form, submitter) {
    var btns = submitButtonsOf(form, submitter);
    form._mfhBusy = btns;
    btns.forEach(function (b) {
      b.setAttribute('aria-busy', 'true');
      var text = b.getAttribute('data-loading-text');
      if (text) {
        if (b.tagName === 'INPUT') { b._mfhOrig = b.value; b.value = text; }
        else {
          b._mfhOrig = b.innerHTML;
          b.textContent = text;
        }
      }
    });
    // Disable after the browser has built the form data, so a submitter's own name/value is still sent.
    setTimeout(function () { btns.forEach(function (b) { b.disabled = true; }); }, 0);
    form._mfhTimer = setTimeout(function () { restoreForm(form); }, 20000);
  }

  function restoreForm(form) {
    clearTimeout(form._mfhTimer);
    (form._mfhBusy || []).forEach(function (b) {
      b.disabled = false;
      b.removeAttribute('aria-busy');
      if (b._mfhOrig != null) {
        if (b.tagName === 'INPUT') b.value = b._mfhOrig; else b.innerHTML = b._mfhOrig;
        b._mfhOrig = null;
      }
    });
    form._mfhBusy = null;
  }

  function wantsLoading(form) {
    return form.hasAttribute('data-loading') || !!qs('[data-loading-text]', form);
  }

  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    qsa('form').forEach(function (f) { if (f._mfhBusy) restoreForm(f); });
    qsa('[data-toggle-password]').forEach(function (b) {
      var wrap = b.closest('.password-field');
      var input = wrap && qs('input', wrap);
      if (input) setPasswordVisible(b, input, false);
    });
  });

  /* ---------- Confirmation modal ---------- */
  var modalCount = 0;
  MFH.confirm = function (opts) {
    opts = opts || {};
    if (typeof HTMLDialogElement !== 'function') {
      // Very old browsers only: the native prompt is better than skipping the confirmation.
      return Promise.resolve(window.confirm(opts.message || opts.title || 'Are you sure?'));
    }
    return new Promise(function (resolve) {
      var opener = document.activeElement;
      var id = 'mfh-modal-' + (++modalCount);
      var dlg = el('dialog', 'mfh-modal' + (opts.danger ? ' mfh-modal-danger' : ''));
      dlg.setAttribute('aria-labelledby', id + '-title');
      if (opts.message) dlg.setAttribute('aria-describedby', id + '-msg');
      var body = el('div', 'mfh-modal-body');
      var title = el('h2', 'mfh-modal-title', opts.title || 'Are you sure?');
      title.id = id + '-title';
      body.appendChild(title);
      if (opts.message) {
        var msg = el('p', 'mfh-modal-message', opts.message);
        msg.id = id + '-msg';
        body.appendChild(msg);
      }
      var actions = el('div', 'mfh-modal-actions');
      var cancel = el('button', 'btn btn-secondary', opts.cancelText || 'Cancel');
      cancel.type = 'button';
      var ok = el('button', 'btn ' + (opts.danger ? 'btn-danger' : 'btn-primary'), opts.confirmText || 'Confirm');
      ok.type = 'button';
      actions.appendChild(cancel);
      actions.appendChild(ok);
      body.appendChild(actions);
      dlg.appendChild(body);
      document.body.appendChild(dlg);

      var result = false, done = false;
      function finish() {
        if (done) return;
        done = true;
        dlg.remove();
        if (opener && opener.focus && document.contains(opener)) opener.focus();
        resolve(result);
      }
      ok.addEventListener('click', function () { result = true; dlg.close(); });
      cancel.addEventListener('click', function () { dlg.close(); });
      // The backdrop is part of the dialog element; the body fills the dialog, so a click on the dialog itself is a backdrop click.
      dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
      dlg.addEventListener('close', finish);
      dlg.addEventListener('cancel', function () { result = false; }); // Esc; the browser then fires close
      // showModal() makes the rest of the page inert, which is the focus trap; Tab cycles inside the dialog.
      dlg.showModal();
      (opts.danger ? cancel : ok).focus();
    });
  };

  function confirmOptsFrom(node) {
    var d = node.dataset;
    return {
      title: d.confirmTitle || 'Please confirm',
      message: d.confirm,
      confirmText: d.confirmText || 'Confirm',
      cancelText: d.confirmCancel || 'Cancel',
      danger: d.confirmDanger != null || node.classList.contains('btn-danger')
    };
  }

  function resubmit(form, submitter) {
    form._mfhConfirmed = true;
    if (typeof form.requestSubmit === 'function') form.requestSubmit(submitter && submitter.form === form ? submitter : undefined);
    else { form.submit(); }
  }

  document.addEventListener('click', function (e) {
    var node = e.target.closest && e.target.closest('a[data-confirm], button[data-confirm], input[data-confirm]');
    if (!node || e.defaultPrevented) return;
    if (node._mfhConfirmed) { node._mfhConfirmed = false; return; }
    if (node.tagName === 'A') {
      e.preventDefault();
      MFH.confirm(confirmOptsFrom(node)).then(function (yes) {
        if (!yes) return;
        node._mfhConfirmed = true;
        node.click();
      });
    } else if (node.form && (node.type === 'submit' || !node.type)) {
      e.preventDefault();
      MFH.confirm(confirmOptsFrom(node)).then(function (yes) { if (yes) resubmit(node.form, node); });
    }
  });

  /* ---------- Submit pipeline: validate, confirm, loading ---------- */
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement) || e.defaultPrevented) return;
    if (form._mfhBusy) { e.preventDefault(); return; } // double submit
    if (form.hasAttribute('data-validate') && !MFH.validateForm(form)) { e.preventDefault(); return; }
    var submitter = e.submitter || null;
    if (form.hasAttribute('data-confirm') && !form._mfhConfirmed) {
      e.preventDefault();
      MFH.confirm(confirmOptsFrom(form)).then(function (yes) { if (yes) resubmit(form, submitter); });
      return;
    }
    form._mfhConfirmed = false;
    if (wantsLoading(form)) setLoading(form, submitter);
  });

  /* ---------- Copy to clipboard ---------- */
  function fallbackCopy(text) {
    var ta = el('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
    ta.remove();
    return ok ? Promise.resolve() : Promise.reject(new Error('copy failed'));
  }

  MFH.copy = function (text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () { return fallbackCopy(text); });
    }
    return fallbackCopy(text);
  };

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-copy], [data-copy-target]');
    if (!btn) return;
    var text = btn.getAttribute('data-copy');
    if (text == null) {
      var target = qs(btn.getAttribute('data-copy-target'));
      if (!target) return;
      text = 'value' in target ? target.value : target.textContent.trim();
    }
    MFH.copy(text).then(function () {
      if (typeof MFH.toast === 'function') {
        MFH.toast('Copied', 'success');
      } else {
        var label = qs('.copy-label', btn) || btn;
        if (btn._mfhCopyText == null) btn._mfhCopyText = label.textContent;
        label.textContent = 'Copied';
        btn.setAttribute('data-copied', 'true');
        clearTimeout(btn._mfhCopyTimer);
        btn._mfhCopyTimer = setTimeout(function () {
          label.textContent = btn._mfhCopyText;
          btn._mfhCopyText = null;
          btn.removeAttribute('data-copied');
        }, 2000);
      }
      announce('Copied');
    }, function () {
      if (typeof MFH.toast === 'function') MFH.toast('Could not copy. Select the text and copy it by hand.', 'error');
      else announce('Could not copy. Select the text and copy it by hand.');
    });
  });

  /* ---------- Accordion (native <details>) ---------- */
  // data-accordion="single" keeps one panel open at a time; a #hash that matches a panel id opens it.
  document.addEventListener('toggle', function (e) {
    var d = e.target;
    if (!d.matches || !d.matches('details') || !d.open) return;
    var group = d.closest('[data-accordion="single"]');
    if (!group) return;
    qsa('details[open]', group).forEach(function (o) { if (o !== d) o.open = false; });
  }, true);

  function openFromHash() {
    if (!location.hash || location.hash.length < 2) return;
    var node;
    try { node = document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch (err) { return; }
    if (node && node.matches('details') && node.closest('[data-accordion]')) {
      node.open = true;
      node.scrollIntoView();
    }
  }
  window.addEventListener('hashchange', openFromHash);

  /* ---------- Init ---------- */
  MFH.initComponents = function (scope) {
    initPasswordToggles(scope);
    initValidation(scope);
  };

  function ready() {
    MFH.initComponents(document);
    openFromHash();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();
})();
