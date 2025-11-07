document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('[data-bs-toggle="dropdown"]').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.nextElementSibling?.classList.toggle('show');
    });
  });
});