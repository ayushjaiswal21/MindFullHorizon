// Tip of the day: asks the server for today's tip (which may start the once-a-day model call) and swaps the text in.
// The card already shows a vetted static tip, so nothing here is required. Server text is set with textContent only.
(function () {
  'use strict';
  var card = document.getElementById('tip-card');
  if (!card) return;
  fetch(card.getAttribute('data-src'), { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (d) {
      if (d && d.source === 'model' && typeof d.text === 'string' && d.text) {
        card.querySelector('[data-tip-text]').textContent = d.text;
        card.setAttribute('data-tip-source', 'model');
      }
    })
    .catch(function () {});
})();
