document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.mood-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const mood = btn.dataset.mood;
      const res = await fetch('/api/mood', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mood, value: 5})
      });
      const json = await res.json();
      if (res.ok) btn.classList.add('selected');
      else alert(json.error || 'Mood save failed');
    });
  });
});