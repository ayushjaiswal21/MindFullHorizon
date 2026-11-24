/* Catalogue form: POST /admin/api/catalogue (new) or PUT /admin/api/catalogue/<id> (edit). Field errors from `fields`. */
(function () {
  'use strict';
  var MFH = window.MFH;
  var form = document.getElementById('catalogue-form');
  if (!form) return;
  var NAMES = ['generic_name', 'brand_name', 'strength', 'form', 'route', 'tpg_list', 'schedule', 'therapeutic_class'];
  var status = document.getElementById('form-status'), formErr = document.getElementById('form-error');

  function clearErrors() {
    formErr.hidden = true;
    NAMES.forEach(function (n) {
      var inp = document.getElementById('m-' + n), msg = document.getElementById('m-' + n + '-err');
      if (inp) inp.removeAttribute('aria-invalid');
      if (msg) { msg.hidden = true; msg.textContent = ''; }
    });
  }

  function showErrors(e) {
    var first = null;
    Object.keys(e.fields || {}).forEach(function (n) {
      var inp = document.getElementById('m-' + n), msg = document.getElementById('m-' + n + '-err');
      if (!inp || !msg) return;
      inp.setAttribute('aria-invalid', 'true');
      msg.textContent = e.fields[n]; msg.hidden = false;
      if (!first) first = inp;
    });
    if (first) first.focus();
    else { formErr.textContent = e.message; formErr.hidden = false; }
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    clearErrors();
    var body = { active: document.getElementById('m-active').checked };
    NAMES.forEach(function (n) { body[n] = document.getElementById('m-' + n).value.trim(); });
    var id = form.getAttribute('data-id'), api = form.getAttribute('data-api');
    var btn = form.querySelector('button[type="submit"]');
    MFH.busy(btn, true);
    MFH.say(status, 'Saving.');
    MFH.api(id ? 'PUT' : 'POST', id ? api + '/' + id : api, body).then(function () {
      MFH.toast('Medicine saved', 'success');
      MFH.say(status, 'Saved.');
      window.location.href = form.getAttribute('data-list-url');
    }, function (e) {
      MFH.say(status, 'The medicine was not saved.');
      showErrors(e);
      MFH.busy(btn, false);
    });
  });
})();
