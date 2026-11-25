// In-page measurement for specs/layout_sweep.mjs. `probe` is serialised by Playwright, so it must stay self-contained.
export function probe({ touch }) {
  const iw = window.innerWidth, ih = window.innerHeight;
  const cs = (e) => getComputedStyle(e);
  const sig = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
    (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
  const shown = (e) => {
    const r = e.getBoundingClientRect(), s = cs(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !e.closest('[hidden],[inert],dialog:not([open])');
  };
  const out = { overflow: 0, first: '', tap: [], clip: [], imgs: [], cover: 0, coverBy: '' };

  // 1. horizontal overflow: scroll width, plus the furthest right edge of any element not clipped by a scroll
  // container (body has overflow-x: clip, so overflowing content is cut off rather than scrollable)
  out.overflow = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - iw;
  let worst = 0;
  for (const e of document.body.querySelectorAll('*')) {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.right <= iw + 1 || r.right - iw <= worst || !shown(e) || cs(e).position === 'fixed') continue;
    let clipped = false;
    for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = cs(p);
      if (s.position === 'fixed' || (s.overflowX !== 'visible' && p.getBoundingClientRect().right <= iw + 1)) { clipped = true; break; }
    }
    if (!clipped) { worst = Math.round(r.right - iw); out.first = sig(e) + ' right=' + Math.round(r.right) + ' w=' + Math.round(r.width); }
  }
  out.overflow = Math.max(out.overflow, worst);

  // 2. touch targets under 44x44 (only meaningful on touch widths); links inside running text are exempt
  if (touch) {
    const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=tab],[role=menuitem]';
    for (const e of document.querySelectorAll(sel)) {
      if (e.closest('.sr-only,.skip-link,.mfh-honeypot,.mfh-visually-hidden') || e.disabled) continue;
      let box = e;
      if (e.matches('input[type=checkbox],input[type=radio]')) box = (e.labels && e.labels[0]) || e.closest('label') || e;
      const r = box.getBoundingClientRect();
      if (!shown(box) && !(box !== e && shown(e))) continue;
      if (r.width <= 2 || r.height <= 2) continue; // visually hidden control, its label is the target
      if (e.tagName === 'A') {
        const host = e.closest('p,li,dd,td,label,.prose,.help,.alert,.lead,.muted,.consent-copy');
        const hostText = host ? host.textContent.replace(/\s+/g, ' ').trim().length : 0;
        const own = e.textContent.replace(/\s+/g, ' ').trim().length;
        if (host && host !== e && hostText > own + 12 && cs(e).display === 'inline') continue;
      }
      if (r.width < 43.5 || r.height < 43.5) out.tap.push(sig(box) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' "' + (box.textContent || box.getAttribute('aria-label') || '').trim().slice(0, 20) + '"');
    }
  }

  // 3. text clipped by overflow:hidden (deliberate text-overflow:ellipsis is not reported)
  for (const e of document.body.querySelectorAll('*')) {
    const s = cs(e);
    if (s.overflowX === 'visible' || s.overflowX === 'auto' || s.overflowX === 'scroll' || s.textOverflow === 'ellipsis') continue;
    if (e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 4 && !e.closest('.mfh-honeypot,.mfh-visually-hidden') && (e.innerText || '').trim() && shown(e) && !e.closest('.sr-only,svg,canvas')) {
      out.clip.push(sig(e) + ' scroll=' + e.scrollWidth + ' client=' + e.clientWidth);
    }
  }

  // 4. images without width and height attributes (they cause layout shift)
  for (const img of document.querySelectorAll('img')) {
    if (!(img.getAttribute('width') && img.getAttribute('height'))) out.imgs.push((img.getAttribute('src') || '').slice(0, 50));
  }

  // 5. fixed or sticky layers (outermost only) covering more than 40 percent of the viewport height
  let total = 0, names = [];
  for (const e of document.body.querySelectorAll('*')) {
    const pos = cs(e).position;
    if ((pos !== 'fixed' && pos !== 'sticky') || !shown(e) || e.closest('dialog,[aria-modal=true]')) continue;
    if (e.parentElement && e.parentElement.closest('[style*="position: fixed"],.consent-banner,.site-header')) continue;
    const r = e.getBoundingClientRect();
    const h = Math.max(0, Math.min(r.bottom, ih) - Math.max(r.top, 0));
    if (h > 0 && r.width > iw * 0.5) { total += h; names.push(sig(e) + ' ' + Math.round(h)); }
  }
  out.cover = Math.round((total / ih) * 100);
  out.coverBy = names.join(', ');
  return out;
}
