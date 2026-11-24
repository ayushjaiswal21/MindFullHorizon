// "Log as taken": POST with fetch and show the result instead of navigating to raw JSON.
// The server checks that the medication belongs to the session user.
document.addEventListener('DOMContentLoaded', function () {
  var csrf = document.querySelector('meta[name="csrf-token"]');
  var note = document.getElementById('med-feedback');

  function say(text, ok) {
    if (window.MFH && typeof window.MFH.toast === 'function') {
      window.MFH.toast(text, ok ? 'success' : 'error');
      return;
    }
    note.textContent = text;
    note.className = 'alert ' + (ok ? 'alert-success' : 'alert-danger');
    note.hidden = false;
  }

  function markLogged(form) {
    var badge = document.createElement('span');
    badge.className = 'badge badge-success';
    badge.textContent = 'Logged today';
    form.textContent = '';
    form.appendChild(badge);
  }

  document.querySelectorAll('.log-med-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = form.querySelector('button[type="submit"]');
      if (!btn || btn.disabled) return;
      var label = btn.textContent;
      btn.disabled = true;
      btn.setAttribute('aria-busy', 'true');
      btn.textContent = btn.getAttribute('data-loading-text') || 'Saving';
      fetch(form.action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: Object.assign({
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/x-www-form-urlencoded'
        }, csrf ? { 'X-CSRFToken': csrf.content } : {}),
        body: new URLSearchParams({ medication_id: form.dataset.medId })
      }).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (json) { return { res: res, json: json }; });
      }).then(function (r) {
        var done = r.res.ok && r.json.success;
        say(r.json.message || (done ? 'Logged.' : 'Could not log this medication.'), done);
        if (done || (r.res.ok && /already/i.test(r.json.message || ''))) markLogged(form);
        else { btn.disabled = false; btn.removeAttribute('aria-busy'); btn.textContent = label; }
      }).catch(function () {
        say('Network problem. Try again.', false);
        btn.disabled = false; btn.removeAttribute('aria-busy'); btn.textContent = label;
      });
    });
  });
});
