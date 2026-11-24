// "Log as Taken": post with fetch and show the result instead of navigating to raw JSON.
document.addEventListener('DOMContentLoaded', () => {
  const csrf = document.querySelector('meta[name="csrf-token"]');
  const note = document.getElementById('med-feedback');

  function say(text, ok) {
    note.textContent = text;
    note.className = 'fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-md shadow-lg text-white ' + (ok ? 'bg-green-600' : 'bg-gray-700');
    setTimeout(() => note.classList.add('hidden'), 4000);
  }

  document.querySelectorAll('.log-med-form').forEach(form => {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      try {
        const res = await fetch(form.action, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
            ...(csrf ? { 'X-CSRFToken': csrf.content } : {})
          },
          body: new URLSearchParams({ medication_id: form.dataset.medId })
        });
        const json = await res.json().catch(() => ({}));
        const done = res.ok && json.success;
        say(json.message || (done ? 'Logged.' : 'Could not log this medication.'), done);
        if (done || (res.ok && /already/i.test(json.message || ''))) {
          btn.textContent = 'Logged';
          btn.className = 'bg-green-500 text-white font-bold py-2 px-4 rounded-md cursor-not-allowed';
        } else {
          btn.disabled = false;
        }
      } catch (err) {
        say('Network problem. Please try again.', false);
        btn.disabled = false;
      }
    });
  });
});
