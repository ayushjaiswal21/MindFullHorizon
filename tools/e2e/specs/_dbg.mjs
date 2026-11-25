import { launch, login, B } from '../lib.mjs';
const [role, path, w] = process.argv.slice(2);
const { browser, page } = await launch('light');
await page.setViewportSize({ width: +w, height: 800 });
if (role === 'admin') { await page.goto(B + '/admin/login'); await page.fill('input[name=email]', 'demo.admin@example.com'); await page.fill('input[name=password]', 'Demo@Pass2026'); await page.click('form:has(input[name=password]) button[type=submit]'); await page.waitForLoadState('networkidle'); }
else await login(page, role === 'doctor' ? 'demo.doctor@example.com' : 'demo.patient@example.com', role === 'doctor' ? 'provider' : 'patient');
await page.goto(B + path, { waitUntil: 'networkidle' });
const r = await page.evaluate(() => {
  const iw = innerWidth, out = [];
  document.querySelectorAll('body *').forEach(e => { const b = e.getBoundingClientRect(); if (b.width && b.right > iw + 1) { const s = getComputedStyle(e); out.push(e.tagName + '.' + String(e.className).slice(0, 50) + '#' + e.id + ' L=' + Math.round(b.left) + ' R=' + Math.round(b.right) + ' pos=' + s.position + ' ox=' + s.overflowX); } });
  return { sw: document.documentElement.scrollWidth, bsw: document.body.scrollWidth, iw, out: out.slice(0, 8) };
});
console.log(JSON.stringify(r, null, 1));
await browser.close();
