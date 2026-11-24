/* Appointment form: show the video / in-person choice and the e-prescription consent only when a doctor is
   selected. Doctor ids come from the form's data-doctor-ids attribute. Without JavaScript the fields stay visible. */
(function () {
  'use strict';
  var form = document.querySelector('form[data-doctor-ids]');
  var select = document.getElementById('provider');
  var box = document.querySelector('[data-doctor-only]');
  if (!form || !select || !box) return;
  var doctors = (form.getAttribute('data-doctor-ids') || '').split(',').filter(Boolean);

  function sync() {
    var isDoctor = doctors.indexOf(select.value) !== -1;
    box.hidden = !isDoctor;
    Array.prototype.forEach.call(box.querySelectorAll('input'), function (el) { el.disabled = !isDoctor; });
  }
  select.addEventListener('change', sync);
  sync();
})();
