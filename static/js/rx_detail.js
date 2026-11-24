/* Prescription detail: cancel (reason dialog) and amend (new draft). docs/CLINICAL_DESIGN.md 3.8, 5.3.
   POST .../cancel {reason_code}, POST .../amend returns the new draft. */
(function () {
  'use strict';
  var dlg = document.getElementById('rd-dialog');
  var cancelBtn = document.getElementById('rd-cancel'), amendBtn = document.getElementById('rd-amend');
  var cfg, live = document.getElementById('rd-status'), box = document.getElementById('rd-alert');

  function show(msg) { document.getElementById('rd-alert-text').textContent = msg; box.hidden = !msg; }
  function fail(err) { if (!err.aborted) { show(err.message); MFH.say(live, err.message); } }

  function cancel() {
    var ok = document.getElementById('rd-dialog-ok');
    MFH.busy(ok, true); show('');
    MFH.api('POST', cfg.cancel, { reason_code: document.getElementById('rd-reason').value }).then(function () {
      dlg.close();
      window.location.reload();
    }, function (err) { dlg.close(); MFH.busy(ok, false); fail(err); });
  }

  function amend() {
    MFH.ask({ title: 'Write a corrected prescription?', message: 'A new draft is created with the same details. This prescription stays valid until you issue the new one, then it is cancelled.', confirmText: 'Create draft' }).then(function (yes) {
      if (!yes) return null;
      MFH.busy(amendBtn, true);
      return MFH.api('POST', cfg.amend, {}).then(function (r) {
        var d = r.prescription || r.draft || r;
        window.location.href = cfg.prescribe + '?draft_id=' + encodeURIComponent(d.id) + '&step=2';
      }, function (err) { MFH.busy(amendBtn, false); fail(err); });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    cfg = MFH.cfg();
    if (/[?&]issued=1/.test(window.location.search)) {
      MFH.toast('Prescription issued. You can print it from this page.', 'success');
      if (window.history && history.replaceState) history.replaceState(null, '', window.location.pathname);
    }
    if (cancelBtn && dlg && dlg.showModal) {
      cancelBtn.addEventListener('click', function () { dlg.showModal(); });
      document.getElementById('rd-dialog-close').addEventListener('click', function () { dlg.close(); });
      document.getElementById('rd-dialog-ok').addEventListener('click', cancel);
    }
    if (amendBtn) amendBtn.addEventListener('click', amend);
  });
})();
