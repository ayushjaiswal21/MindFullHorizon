/* Verification detail: Verify, Reject, Suspend, Reinstate. Posts {checks, note} after a confirmation. */
(function () {
  'use strict';
  var MFH = window.MFH;
  var form = document.getElementById('verify-form');
  if (!form) return;
  var note = document.getElementById('v-note'), err = document.getElementById('v-error'), live = document.getElementById('v-live');
  var needChecks = { verify: true, reinstate: true };
  var COPY = {
    verify: ['Verify this doctor?', 'They will be able to prescribe until the review date. You are confirming that you checked the register entry.', 'Verify', false, 'Doctor verified'],
    reinstate: ['Reinstate this doctor?', 'Prescribing is switched on again after the check you just recorded.', 'Reinstate', false, 'Doctor reinstated'],
    reject: ['Reject this registration?', 'The doctor cannot prescribe and can correct the details and send them again.', 'Reject', true, 'Registration rejected'],
    suspend: ['Suspend this doctor?', 'Prescribing stops on their next request and their issued prescriptions cannot be dispensed.', 'Suspend', true, 'Doctor suspended']
  };

  function problem(msg, focus) {
    err.textContent = msg; err.hidden = false;
    if (focus) focus.focus();
    return false;
  }

  function collect(act) {
    err.hidden = true;
    var checks = {}, boxes = form.querySelectorAll('[data-check]'), missing = null;
    [].forEach.call(boxes, function (b) { checks[b.getAttribute('data-check')] = b.checked; if (!b.checked && !missing) missing = b; });
    if (needChecks[act] && missing) { problem('Tick every box in the checklist before you ' + act + '.', missing); return null; }
    var text = note.value.trim();
    if (text.length < 10 || text.length > 500) { problem('Write an evidence note or reason of 10 to 500 characters.', note); return null; }
    return { checks: checks, note: text };
  }

  form.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-vact]');
    if (!btn || btn.disabled) return;
    var act = btn.getAttribute('data-vact'), body = collect(act), c = COPY[act];
    if (!body || !c) return;
    MFH.ask({ title: c[0], message: c[1], confirmText: c[2], danger: c[3] }).then(function (yes) {
      if (!yes) return;
      MFH.busy(btn, true);
      MFH.api('POST', form.getAttribute('data-base-url') + '/' + act, body).then(function () {
        MFH.say(live, c[4] + '.');
        MFH.toast(c[4], 'success');
        setTimeout(function () { window.location.reload(); }, 700);
      }, function (e2) {
        problem(e2.message, null);
        MFH.busy(btn, false);
      });
    });
  });
})();
