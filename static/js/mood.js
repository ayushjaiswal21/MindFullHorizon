// static/js/mood.js
document.addEventListener('DOMContentLoaded', () => {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : null;

  function postMood(moodVal) {
    return fetch('/api/save-mood', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
      },
      body: JSON.stringify({ mood: moodVal })
    }).then(async res => {
      const json = await res.json().catch(() => null);
      return { ok: res.ok, status: res.status, json };
    });
  }

  // Bind any .mood-option elements (if present)
  document.querySelectorAll('.mood-option').forEach(el => {
    el.addEventListener('click', () => {
      document.querySelectorAll('.mood-option').forEach(e => e.classList.remove('selected'));
      el.classList.add('selected');
      const btn = document.getElementById('save-mood-btn');
      if (btn) btn.disabled = false;
    });
  });

  // Save button
  const saveBtn = document.getElementById('save-mood-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const sel = document.querySelector('.mood-option.selected');
      if (!sel) {
        alert('Please select a mood first.');
        return;
      }
      const moodVal = sel.getAttribute('data-mood');
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';
      try {
        const { ok, status, json } = await postMood(moodVal);
        if (ok) {
          alert(json?.message || 'Mood saved successfully.');
        } else {
          alert(json?.message || `Failed to save mood (${status})`);
          saveBtn.disabled = false;
        }
      } catch (err) {
        console.error('Error saving mood', err);
        alert('Network error while saving mood.');
        saveBtn.disabled = false;
      } finally {
        saveBtn.textContent = 'Save Today\'s Mood';
      }
    });
  }
});
