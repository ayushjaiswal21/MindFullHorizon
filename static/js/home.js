// Mood check-in on the logged-in home. The endpoint comes from data-url on the form.
(function () {
  var form = document.getElementById('home-mood-form');
  if (!form) return;
  var status = document.getElementById('home-mood-status');
  var save = document.getElementById('home-mood-save');

  function tell(message, type) {
    if (status) status.textContent = message;
    if (window.MFH && MFH.toast) MFH.toast(message, type);
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var picked = form.querySelector('input[name="mood"]:checked');
    if (!picked) return tell('Pick a number from 1 to 10 first.', 'error');
    var token = form.querySelector('input[name="csrf_token"]');
    var note = form.querySelector('input[name="notes"]');
    save.disabled = true;
    save.setAttribute('aria-busy', 'true');
    fetch(form.dataset.url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': token ? token.value : ''
      },
      body: JSON.stringify({ mood: Number(picked.value), notes: note ? note.value : '' })
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (json) { return { ok: res.ok, json: json }; });
    }).then(function (r) {
      if (r.ok && r.json.success) {
        tell(r.json.message || 'Mood saved.', 'success');
        form.reset();
      } else {
        tell(r.json.message || 'Could not save your mood. Try again.', 'error');
      }
    }).catch(function () {
      tell('Could not reach the server. Check your connection and try again.', 'error');
    }).then(function () {
      save.disabled = false;
      save.removeAttribute('aria-busy');
    });
  });
})();
