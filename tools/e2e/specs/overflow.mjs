import { launch, login, B } from '../lib.mjs';
for (const w of [1280, 1024, 768, 390]) {
  const { browser, page } = await launch('light');
  await page.setViewportSize({ width: w, height: 900 });
  await login(page, 'demo.patient@example.com', 'patient');
  for (const p of ['/patient/dashboard', '/chat', '/patient/schedule']) {
    await page.goto(B + p, { waitUntil: 'networkidle' });
    const r = await page.evaluate(() => {
      const iw = window.innerWidth, out = [];
      document.querySelectorAll('body *').forEach(e => { const b = e.getBoundingClientRect(); if (b.width && b.right > iw + 1) out.push(e.tagName + '.' + (e.className || '').toString().slice(0, 40) + '#' + e.id + ' right=' + Math.round(b.right)); });
      return { over: document.documentElement.scrollWidth - iw, first: out.slice(0, 4) };
    });
    console.log(w, p, JSON.stringify(r));
  }
  await browser.close();
}
