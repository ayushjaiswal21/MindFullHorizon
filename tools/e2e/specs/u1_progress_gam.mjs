import { launch, login, B } from '../lib.mjs';
const SC = process.env.SHOTS || '.';
for (const [scheme, vw] of [['light', 1280], ['dark', 390]]) {
  const { browser, page } = await launch(scheme, scheme === 'dark' ? 'reduce' : 'no-preference');
  await page.setViewportSize({ width: vw, height: 900 });
  await login(page, 'demo.patient@example.com');
  let t = Date.now(); await page.goto(B + '/patient/progress', { waitUntil: 'load' });
  console.log(scheme, vw, 'progress load ms', Date.now() - t, '| skeleton shown at load:', await page.isVisible('#suggestions .skeleton').catch(() => false));
  await page.waitForFunction(() => document.getElementById('suggestions').getAttribute('aria-busy') === 'false', null, { timeout: 15000 });
  console.log(' suggestions settled after ms', Date.now() - t, '|', (await page.textContent('#suggestions')).trim().slice(0, 90).replace(/\s+/g, ' '));
  await page.screenshot({ path: `${SC}/u1_progress_${scheme}_${vw}.png`, fullPage: true });
  await page.goto(B + '/patient/dashboard'); await page.waitForLoadState('networkidle');
  console.log(' card:', (await page.textContent('.gam-card')).replace(/\s+/g, ' ').slice(0, 330));
  console.log(' dots', await page.$$eval('.gam-week li', l => l.map(x => x.getAttribute('aria-label')).join(', ')));
  await page.locator('.gam-card').screenshot({ path: `${SC}/u1_card_${scheme}_${vw}.png` });
  await page.goto(B + '/profile'); await page.waitForLoadState('networkidle');
  console.log(' profile has card:', await page.isVisible('.gam-card'));
  console.log(' errors', page.errors);
  await browser.close();
}
