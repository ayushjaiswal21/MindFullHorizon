// Mobile menu: opens, fits the viewport (scrolls inside itself), shows the last item, closes with the toggle and Escape.
//   BASE=http://127.0.0.1:5201 node specs/layout_menu.mjs
import { launch, login, B } from '../lib.mjs';

let bad = 0;
const ACC = [['patient', 'demo.patient@example.com', 'patient'], ['counsellor', 'demo.provider@example.com', 'provider']];
for (const [name, email, role] of ACC) {
  for (const [w, h] of [[360, 560], [1024, 700]]) {
    const { browser, page } = await launch('light');
    await page.setViewportSize({ width: w, height: h });
    await login(page, email, role);
    const e = await page.$('[data-consent="essential"]'); if (e && await e.isVisible()) await e.click();
    await page.goto(B + '/profile', { waitUntil: 'networkidle' });
    await page.click('.menu-toggle');
    const open = await page.evaluate(() => {
      const m = document.querySelector('.site-menu'), r = m.getBoundingClientRect(), last = [...m.querySelectorAll('a,button')].pop();
      m.scrollTop = m.scrollHeight; const lr = last.getBoundingClientRect();
      return { bottom: Math.round(r.bottom), ih: innerHeight, lastVisible: lr.bottom <= innerHeight + 1 && lr.top >= 0, last: (last.textContent || '').trim().slice(0, 20), expanded: document.querySelector('.menu-toggle').getAttribute('aria-expanded') };
    });
    await page.keyboard.press('Escape');
    const afterEsc = await page.getAttribute('.menu-toggle', 'aria-expanded');
    if (afterEsc !== 'false') { await page.click('.menu-toggle'); }
    const closed = await page.getAttribute('.menu-toggle', 'aria-expanded');
    const ok = open.bottom <= open.ih && open.lastVisible && open.expanded === 'true' && closed === 'false';
    if (!ok) bad++;
    console.log(ok ? 'ok      ' : 'PROBLEM ', name, w + 'x' + h, JSON.stringify(open), 'escape closes:', afterEsc === 'false');
    await browser.close();
  }
}
process.exit(bad ? 1 : 0);
