// Daily mood check-in (1 to 10). Posts to /patient/api/save-mood; the server stores it for the session user.
// No points or streaks are attached to mood: do not add any here.
document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('mood-form');
  if (!form) return;
  var saveBtn = document.getElementById('save-mood-btn');
  var errorEl = document.getElementById('mood-error');
  var savedEl = document.getElementById('mood-saved');
  var noteEl = document.getElementById('mood-notes');
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

  function toast(msg, type) {
    if (window.MFH && typeof window.MFH.toast === 'function') window.MFH.toast(msg, type);
  }

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.hidden = !msg;
    form.querySelector('.mood-scale').setAttribute('aria-invalid', msg ? 'true' : 'false');
  }

  form.addEventListener('change', function () { showError(''); savedEl.hidden = true; });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var sel = form.querySelector('input[name="mood"]:checked');
    if (!sel) {
      showError('Choose a number from 1 to 10 before saving.');
      return;
    }
    showError('');
    var label = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.setAttribute('aria-busy', 'true');
    saveBtn.textContent = saveBtn.getAttribute('data-loading-text') || 'Saving';

    fetch('/patient/api/save-mood', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ mood: Number(sel.value), notes: noteEl ? noteEl.value : '' })
    }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (json) {
        return { ok: res.ok, status: res.status, json: json };
      });
    }).then(function (r) {
      if (r.ok) {
        savedEl.textContent = (r.json && r.json.message) || 'Mood saved.';
        savedEl.hidden = false;
        toast('Mood saved.', 'success');
        sel.checked = false;
        if (noteEl) noteEl.value = '';
        document.dispatchEvent(new CustomEvent('mood:saved'));
      } else {
        showError((r.json && r.json.message) || 'Could not save your mood (error ' + r.status + '). Try again.');
      }
    }).catch(function () {
      showError('Could not reach the server. Check your connection and try again.');
    }).then(function () {
      saveBtn.disabled = false;
      saveBtn.removeAttribute('aria-busy');
      saveBtn.textContent = label;
    });
  });
});
