/* Grounding exercise: one step at a time with Next and Back. No animation. Without JS all steps stay visible. */
(function () {
  'use strict';
  var root = document.getElementById('grounding');
  if (!root) return;
  var steps = Array.prototype.slice.call(root.querySelectorAll('.gr-step'));
  var last = steps.length;
  var nav = document.getElementById('gr-nav');
  var back = document.getElementById('gr-back'), next = document.getElementById('gr-next');
  var finish = document.getElementById('gr-finish'), again = document.getElementById('gr-again');
  var progress = document.getElementById('gr-progress'), result = document.getElementById('gr-result');
  var current = 1, saved = false;

  function show(n, focus) {
    current = Math.max(1, Math.min(last, n));
    steps.forEach(function (li, i) { li.hidden = i + 1 !== current; });
    var done = current === last;
    back.hidden = current === 1 || done;
    next.hidden = done;
    finish.hidden = !done || saved;
    again.hidden = !(done && saved);
    progress.textContent = done ? 'Finished' : 'Step ' + current + ' of ' + (last - 1);
    if (focus) steps[current - 1].querySelector('.gr-heading').focus();
  }

  function complete() {
    finish.disabled = true;
    fetch(root.getAttribute('data-complete-url'), {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': window.WL ? WL.csrf() : '',
                 'Idempotency-Key': root.getAttribute('data-request-id') },
      credentials: 'same-origin'
    }).then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function (d) { result.textContent = d.message || 'Saved.'; saved = true; })
      .catch(function () { result.textContent = 'Your exercise could not be saved, but you did it.'; saved = true; })
      .then(function () { finish.disabled = false; show(last, false); });
  }

  nav.hidden = false;
  progress.hidden = false;
  back.addEventListener('click', function () { show(current - 1, true); });
  next.addEventListener('click', function () { show(current + 1, true); });
  finish.addEventListener('click', complete);
  again.addEventListener('click', function () { show(1, true); });
  root.addEventListener('keydown', function (e) {
    if (e.target.closest('a, input, textarea') || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'ArrowRight' && current < last - 1) { e.preventDefault(); show(current + 1, true); }
    if (e.key === 'ArrowLeft' && current > 1 && current < last) { e.preventDefault(); show(current - 1, true); }
  });
  show(1, false);
})();
