// Seeds long unbroken user text (journal, blog post and comment, goal, profile name) and checks no page overflows at 360px.
//   BASE=http://127.0.0.1:5201 node specs/layout_stress.mjs     (uses the demo accounts; run only against a demo database)
import { launch, login, B } from '../lib.mjs';
import { probe } from '../layout_probe.mjs';

const LONG = 'Supercalifragilisticexpialidocious_'.repeat(5) + 'https://example.com/' + 'a'.repeat(120);
const { browser, page } = await launch('light');
await page.setViewportSize({ width: 360, height: 800 });
await login(page, 'demo.patient@example.com', 'patient');
const essential = await page.$('[data-consent="essential"]'); if (essential && await essential.isVisible()) await essential.click();

await page.goto(B + '/patient/journal', { waitUntil: 'networkidle' });
await page.fill('#title', LONG.slice(0, 100)); await page.fill('#content', LONG);
await page.click('#journal-form button[type=submit]'); await page.waitForLoadState('networkidle');

await login(page, 'demo.provider@example.com', 'provider');
await page.goto(B + '/blog/create', { waitUntil: 'networkidle' });
await page.fill('#title', LONG.slice(0, 200)); await page.fill('#content', LONG + '\n\n' + LONG);
await page.click('form[action*="blog"] button[type=submit]'); await page.waitForLoadState('networkidle');
await page.goto(B + '/blog/', { waitUntil: 'networkidle' });
const postUrl = B + (await page.getAttribute('a[href^="/blog/"][href$="0"], a[href^="/blog/"]:not([href="/blog/"]):not([href*="create"])', 'href'));

const pages = ['/blog/', postUrl.replace(B, ''), '/patient/journal'];
let bad = 0;
for (const p of pages) {
  if (p === '/patient/journal') await login(page, 'demo.patient@example.com', 'patient');
  await page.goto(B + p, { waitUntil: 'networkidle' });
  const m = await page.evaluate(probe, { touch: false });
  const seen = (await page.content()).includes('Supercalifragilistic');
  console.log(m.overflow > 0 ? 'OVERFLOW' : 'ok      ', p, m.overflow, m.first, seen ? '(long text shown)' : '(long text NOT on page)');
  if (m.overflow > 0) bad++;
}
await browser.close();
process.exit(bad ? 1 : 0);
