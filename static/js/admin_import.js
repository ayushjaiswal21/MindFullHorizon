/* CSV import box (catalogue and stock): "Check file" does a dry run, "Import" is enabled only after a clean check.
   Assumed response: {success, rows, errors: [{row, code, message}]}. Errors arrive in the body of a 422. */
(function () {
  'use strict';
  var MFH = window.MFH;
  var form = document.getElementById('import-form');
  if (!form) return;
  var file = document.getElementById('import-file'), check = document.getElementById('import-check');
  var run = document.getElementById('import-run'), out = document.getElementById('import-result');

  function note(kind, text, extra) {
    MFH.clear(out);
    out.appendChild(MFH.h('div', { class: 'alert alert-' + kind }, [MFH.icon(kind === 'success' ? 'check' : 'alert'), MFH.h('div', {}, [MFH.h('p', { text: text }), extra])]));
  }

  function errorList(errors) {
    if (!errors || !errors.length) return null;
    var shown = errors.slice(0, 50).map(function (e) {
      return MFH.h('li', { text: (e.row ? 'Row ' + e.row + ': ' : '') + (e.message || e.code || 'Not valid') });
    });
    if (errors.length > 50) shown.push(MFH.h('li', { text: (errors.length - 50) + ' more rows have errors.' }));
    return MFH.h('ul', { class: 'cl-errors' }, shown);
  }

  function send(dry) {
    var f = file.files && file.files[0];
    if (!f) { note('danger', 'Choose a CSV file first.'); return; }
    var fd = new FormData();
    fd.append('file', f);
    fd.append('dry_run', dry ? '1' : '0');
    var btn = dry ? check : run;
    MFH.busy(btn, true);
    MFH.api('POST', form.getAttribute('data-import-url'), fd).then(function (r) {
      var n = r.rows != null ? r.rows + ' rows' : 'The file';
      if (dry) {
        note('success', n + ' checked, no errors. Press Import to save them.');
        run.disabled = false;
      } else {
        note('success', n + ' imported.', MFH.h('a', { class: 'cl-link', href: window.location.href, text: 'Reload the page to see the changes' }));
        MFH.toast('Import finished', 'success');
        run.disabled = true;
      }
    }, function (e) {
      run.disabled = true;
      note('danger', dry ? 'The file has errors. Nothing was saved. Fix them and check the file again.' : (e.message || 'Import failed. Nothing was saved.'), errorList(e.body && e.body.errors));
    }).then(function () { MFH.busy(btn, false); if (dry === false) run.disabled = true; });
  }

  check.addEventListener('click', function () { send(true); });
  run.addEventListener('click', function () { send(false); });
  file.addEventListener('change', function () { run.disabled = true; MFH.clear(out); });
})();
