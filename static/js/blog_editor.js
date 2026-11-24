// Blog create/edit: word count, preview, and (create page only) a draft kept in localStorage on this device.
(function () {
  var form = document.getElementById('blog-form');
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var title = $('title'), category = $('category'), tags = $('tags'), content = $('content');
  var statusEl = $('editor-status');
  var draftKey = form.dataset.draftKey || null;

  function notify(message, type) {
    if (window.MFH && MFH.toast) MFH.toast(message, type);
    if (statusEl) statusEl.textContent = message;
  }

  // localStorage can throw (private mode, blocked storage); the editor must work without it.
  function store(action, value) {
    try {
      if (action === 'get') return localStorage.getItem(draftKey);
      if (action === 'set') return localStorage.setItem(draftKey, value);
      return localStorage.removeItem(draftKey);
    } catch (e) { return null; }
  }

  function updateWordCount() {
    var text = content.value.trim();
    $('wordCount').textContent = text === '' ? 0 : text.split(/\s+/).length;
  }

  function label(value) {
    var text = (value || '').replace('_', ' ');
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function updatePreview() {
    $('previewTitle').textContent = title.value || 'Untitled post';
    $('previewCategory').textContent = label(category.value);
    $('previewTags').textContent = tags.value ? 'Tags: ' + tags.value : '';
    $('previewContent').textContent = content.value || 'Nothing written yet.';
  }

  function togglePreview() {
    var box = $('previewContainer');
    var show = box.hidden;
    if (show) updatePreview();
    box.hidden = !show;
    $('toggle-preview-btn').setAttribute('aria-expanded', show ? 'true' : 'false');
    $('previewToggleText').textContent = show ? 'Hide preview' : 'Show preview';
  }

  function saveDraft(quiet) {
    if (!draftKey) return;
    store('set', JSON.stringify({
      title: title.value, category: category.value, tags: tags.value, content: content.value,
      timestamp: new Date().toISOString()
    }));
    if (!quiet) notify('Draft saved on this device.', 'success');
  }

  function offerDraft() {
    var banner = $('draftBanner');
    var raw = store('get');
    if (!banner || !raw) return;
    var draft;
    try { draft = JSON.parse(raw); } catch (e) { return; }
    if (!draft || (!draft.title && !draft.content)) return;
    var minutes = Math.max(0, Math.round((Date.now() - new Date(draft.timestamp)) / 60000));
    $('draftAge').textContent = 'Saved ' + (minutes < 1 ? 'less than a minute' : minutes + ' minutes') + ' ago.';
    banner.hidden = false;
    $('restore-draft-btn').addEventListener('click', function () {
      title.value = draft.title || '';
      category.value = draft.category || 'general';
      tags.value = draft.tags || '';
      content.value = draft.content || '';
      updateWordCount();
      banner.hidden = true;
      title.focus();
    });
    $('discard-draft-btn').addEventListener('click', function () {
      store('remove');
      banner.hidden = true;
    });
  }

  content.addEventListener('input', updateWordCount);
  $('toggle-preview-btn').addEventListener('click', togglePreview);
  updateWordCount();

  if (draftKey) {
    offerDraft();
    var save = $('save-draft-btn');
    if (save) save.addEventListener('click', function () { saveDraft(false); });
    setInterval(function () { if (title.value || content.value) saveDraft(true); }, 30000);
    form.addEventListener('submit', function () { store('remove'); });
  }
})();
