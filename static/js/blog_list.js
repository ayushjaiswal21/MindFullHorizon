// Delete confirmation for the blog list: a native dialog element.
(function () {
  var dialog = document.getElementById('deleteModal');
  var form = document.getElementById('deleteForm');
  var title = document.getElementById('deletePostTitle');
  var cancel = document.getElementById('hide-delete-modal-btn');
  if (!dialog || !form) return;
  var opener = null;

  function open(button) {
    opener = button;
    title.textContent = button.dataset.postTitle || 'this post';
    form.action = '/blog/' + encodeURIComponent(button.dataset.postId) + '/delete';
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    cancel.focus();
  }

  function close() {
    if (typeof dialog.close === 'function') dialog.close(); else dialog.removeAttribute('open');
    if (opener) opener.focus();
  }

  document.querySelectorAll('.confirm-delete-btn').forEach(function (button) {
    button.addEventListener('click', function () { open(button); });
  });
  cancel.addEventListener('click', close);
  // Click on the backdrop (the dialog element itself) closes it.
  dialog.addEventListener('click', function (event) { if (event.target === dialog) close(); });
})();
