/* Wellbeing pages: the print button of the safety plan. No Jinja, no inline handlers (CSP). */
(function () {
  'use strict';
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-print-page]');
    if (btn) { e.preventDefault(); window.print(); }
  });
})();
