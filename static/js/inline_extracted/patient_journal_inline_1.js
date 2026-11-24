/* Journal page: character counter, "show more" paging, and delete with a confirmation dialog. */
(function () {
  'use strict';
  var root = document.getElementById('journal-root');
  if (!root || window.__mfhJournal) return;
  window.__mfhJournal = true;

  var $ = function (id) { return document.getElementById(id); };
  var pageSize = parseInt(root.dataset.pageSize, 10) || 10;
  var list = $('journal-list');

  /* Counter */
  var content = $('content'), counter = $('content-count');
  if (content && counter) {
    var max = parseInt(content.getAttribute('maxlength'), 10) || 5000;
    var update = function () {
      var left = max - content.value.length;
      counter.textContent = content.value.length >= max - 500 ? left + ' left.' : '';
    };
    content.addEventListener('input', update);
    update();
  }

  /* Paging */
  var more = $('show-more-btn'), moreStatus = $('show-more-status');
  function updateCount() {
    var total = list.querySelectorAll('.journal-entry').length;
    var badge = $('entry-count');
    if (badge) badge.textContent = '(' + total + ')';
    $('journal-empty').hidden = total > 0;
  }
  function updateMore() {
    if (!more) return;
    var hidden = list.querySelectorAll('.journal-entry[hidden]').length;
    var shown = list.querySelectorAll('.journal-entry:not([hidden])').length;
    more.hidden = hidden === 0;
    moreStatus.textContent = 'Showing ' + shown + ' of ' + (shown + hidden) + '.';
  }
  if (more) {
    more.addEventListener('click', function () {
      var items = list.querySelectorAll('.journal-entry[hidden]');
      var firstNew = items[0];
      for (var i = 0; i < Math.min(pageSize, items.length); i++) items[i].hidden = false;
      updateMore();
      if (firstNew) { var h = firstNew.querySelector('h3'); if (h) { h.tabIndex = -1; h.focus(); } }
    });
    updateMore();
  }

  /* Delete */
  list.addEventListener('click', function (e) {
    var btn = e.target.closest('.delete-journal-entry-btn');
    if (!btn) return;
    var id = btn.dataset.entryId;
    var card = btn.closest('.journal-entry');
    if (!window.WL || !id) return;
    WL.ask({ title: 'Delete this entry?', message: 'It is removed from your account and cannot be brought back.', confirmText: 'Delete entry', danger: true })
      .then(function (yes) {
        if (!yes) return;
        btn.disabled = true;
        btn.setAttribute('aria-busy', 'true');
        return WL.api('/api/delete-journal-entry/' + encodeURIComponent(id), { method: 'DELETE' }).then(function (r) {
          if (r.ok && r.data && r.data.success) {
            if (card) card.remove();
            updateCount();
            updateMore();
            WL.toast('Entry deleted.', 'success');
            var focusTarget = $('title');
            if (focusTarget) focusTarget.focus();
          } else {
            btn.disabled = false;
            btn.removeAttribute('aria-busy');
            WL.toast('Could not delete the entry. Try again.', 'error');
          }
        });
      })
      .catch(function () {
        btn.disabled = false;
        btn.removeAttribute('aria-busy');
        WL.toast('Could not delete the entry. Check your connection and try again.', 'error');
      });
  });
})();
