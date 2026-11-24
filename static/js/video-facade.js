/* Click-to-load YouTube facade: the iframe (youtube-nocookie.com) is created only after a click or Enter/Space on the thumbnail button. */
(function () {
  'use strict';
  if (window.__mfhFacade) return;
  window.__mfhFacade = true;

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.video-facade');
    if (!btn) return;
    var frame = btn.closest('.video-frame');
    var id = frame && frame.dataset.videoId;
    if (!id || !/^[A-Za-z0-9_-]{11}$/.test(id)) return;
    var iframe = document.createElement('iframe');
    iframe.src = 'https://www.youtube-nocookie.com/embed/' + id + '?rel=0';
    iframe.title = frame.dataset.title || 'Yoga video';
    iframe.allow = 'encrypted-media; picture-in-picture';
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    iframe.allowFullscreen = true;
    iframe.width = 560;
    iframe.height = 315;
    btn.replaceWith(iframe);
    iframe.focus();
  });
})();
