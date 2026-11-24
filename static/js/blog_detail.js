// Blog post page: like, comment, reply, share, delete dialog.
// URLs come from data-* attributes on #blog-root. User text is inserted with textContent only, never parsed as HTML.
(function () {
  var root = document.getElementById('blog-root');
  if (!root) return;
  var URLS = { like: root.dataset.likeUrl, comment: root.dataset.commentUrl, replies: root.dataset.repliesUrl };
  var statusEl = document.getElementById('blog-status');

  function notify(message, type) {
    if (window.MFH && MFH.toast) MFH.toast(message, type);
    if (statusEl) statusEl.textContent = message;
  }

  function csrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json(); });
  }

  function commentNode(c) {
    var node = document.getElementById('comment-template').content.firstElementChild.cloneNode(true);
    node.dataset.commentId = c.id;
    node.querySelector('[data-slot=author]').textContent = c.author_name;
    node.querySelector('[data-slot=date]').textContent = c.created_at;
    node.querySelector('[data-slot=content]').textContent = c.content;
    return node;
  }

  function replyNode(r) {
    var box = document.createElement('div');
    box.className = 'reply';
    var head = document.createElement('div');
    head.className = 'comment-head';
    var who = document.createElement('strong');
    who.textContent = r.author_name;
    var when = document.createElement('time');
    when.textContent = r.created_at;
    head.append(who, when);
    var body = document.createElement('p');
    body.textContent = r.content;
    box.append(head, body);
    return box;
  }

  function toggleLike() {
    post(URLS.like).then(function (data) {
      if (!data.success) return notify(data.message || 'Log in to like posts.', 'error');
      var btn = document.getElementById('likeBtn');
      btn.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
      document.getElementById('likeLabel').textContent = data.liked ? 'Liked' : 'Like';
      document.getElementById('likeCount').textContent = data.like_count;
    }).catch(function () { notify('Could not update your like. Try again.', 'error'); });
  }

  function addComment() {
    var box = document.getElementById('commentText');
    var content = box.value.trim();
    if (!content) return notify('Write a comment first.', 'error');
    post(URLS.comment, { content: content }).then(function (data) {
      if (!data.success) return notify(data.message || 'Could not add your comment.', 'error');
      box.value = '';
      var none = document.getElementById('noComments');
      if (none) none.remove();
      document.getElementById('commentsList').appendChild(commentNode(data.comment));
      document.getElementById('commentCount').textContent = data.comment_count;
      notify('Comment added.', 'success');
    }).catch(function () { notify('Could not add your comment. Try again.', 'error'); });
  }

  function toggleReplyForm(id) {
    var form = document.getElementById('replyForm-' + id);
    if (!form) return;
    form.hidden = !form.hidden;
    if (!form.hidden) {
      var field = document.getElementById('replyText-' + id);
      if (field) field.focus();
    }
  }

  function addReply(id) {
    var box = document.getElementById('replyText-' + id);
    var content = box.value.trim();
    if (!content) return notify('Write a reply first.', 'error');
    post(URLS.comment, { content: content, parent_id: Number(id) }).then(function (data) {
      if (!data.success) return notify(data.message || 'Could not add your reply.', 'error');
      box.value = '';
      toggleReplyForm(id);
      loadReplies(id);
      document.getElementById('commentCount').textContent = data.comment_count;
    }).catch(function () { notify('Could not add your reply. Try again.', 'error'); });
  }

  function loadReplies(id) {
    fetch(URLS.replies.replace(/0\/replies$/, id + '/replies'), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var box = document.getElementById('replies-' + id);
        if (box) box.replaceChildren.apply(box, (data.replies || []).map(replyNode));
      })
      .catch(function () { /* replies stay hidden; the comment itself is already visible */ });
  }

  function sharePost() {
    var title = root.dataset.title;
    if (navigator.share) {
      navigator.share({ title: title, url: location.href }).catch(function () { /* user cancelled */ });
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(location.href)
        .then(function () { notify('Link copied.', 'success'); })
        .catch(function () { notify('Copy this link: ' + location.href, 'info'); });
    } else {
      notify('Copy this link: ' + location.href, 'info');
    }
  }

  function deleteDialog(show) {
    var dialog = document.getElementById('deleteModal');
    if (!dialog) return;
    if (show) {
      if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    } else if (typeof dialog.close === 'function') {
      dialog.close();
    } else {
      dialog.removeAttribute('open');
    }
  }

  var actions = {
    like: toggleLike,
    comment: addComment,
    share: sharePost,
    'delete-open': function () { deleteDialog(true); },
    'delete-close': function () { deleteDialog(false); }
  };

  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    if (el.dataset.action === 'reply-toggle') return toggleReplyForm(el.dataset.id);
    if (el.dataset.action === 'reply-send') return addReply(el.dataset.id);
    if (actions[el.dataset.action]) actions[el.dataset.action]();
  });

  document.querySelectorAll('.comment[data-comment-id]').forEach(function (c) {
    if (c.dataset.commentId) loadReplies(c.dataset.commentId);
  });
})();
