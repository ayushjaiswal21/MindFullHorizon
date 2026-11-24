// Appointment form: earliest bookable date is today (the server checks it again), and a per-page request id
// lets the server ignore a double submit (see utils/idempotency.py).
document.addEventListener('DOMContentLoaded', function () {
  var date = document.getElementById('date');
  if (!date) return;
  var rid = document.getElementById('client-request-id');
  if (rid && window.crypto && crypto.randomUUID) rid.value = crypto.randomUUID();
  var now = new Date();
  var pad = function (n) { return String(n).padStart(2, '0'); };
  date.min = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate());
});
