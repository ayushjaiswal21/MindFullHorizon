// Breathing guide (real-time phases, reduced-motion toggle) and the compact landing helpline card.
// Run: BASE=http://127.0.0.1:5103 SHOTS=<dir> node specs/breathing.mjs
import { launch, login, B } from '../lib.mjs';
import { mkdirSync } from 'node:fs';

const SHOTS = process.env.SHOTS || '.';
mkdirSync(SHOTS, { recursive: true });
let failed = 0;
const check = (ok, msg) => { console.log((ok ? 'PASS ' : 'FAIL ') + msg); if (!ok) failed++; };

// Sample the circle width and the phase word inside the page every 250 ms for `ms`.
const sample = (page, ms) => page.evaluate(async (ms) => {
  const out = [], t0 = performance.now();
  while (performance.now() - t0 < ms) {
    out.push({ t: Math.round(performance.now() - t0),
      w: Math.round(document.getElementById('breathing-circle').getBoundingClientRect().width * 10) / 10,
      phase: document.getElementById('breathing-instruction').textContent,
      count: document.getElementById('breathing-text').textContent });
    await new Promise(r => setTimeout(r, 250));
  }
  return out;
}, ms);
const order = (s) => s.map(x => x.phase).filter(p => p !== 'Ready').filter((p, i, a) => i === 0 || p !== a[i - 1]);
const widthAt = (s, from, to) => s.filter(x => x.t >= from && x.t <= to).map(x => x.w);

async function openGuide(scheme, reduced) {
  const env = await launch(scheme, reduced);
  await login(env.page, 'demo.patient@example.com');
  await env.page.setViewportSize({ width: 1280, height: 1500 });
  await env.page.goto(B + '/patient/breathing');
  const dismiss = env.page.getByRole('button', { name: 'Essential only' });
  if (await dismiss.isVisible()) await dismiss.click();
  return env;
}

// 1. Default motion: box breathing over about 13 seconds.
{
  const { browser, page } = await openGuide('light', 'no-preference');
  await page.locator('#breathing-root').screenshot({ path: SHOTS + '/breathing-light-idle.png' });
  await page.click('#start-btn');
  const s = await sample(page, 13000);
  console.log('phases seen:', order(s).join(' > '));
  check(JSON.stringify(order(s)) === JSON.stringify(['Inhale', 'Hold', 'Exhale', 'Hold']), 'box phase order Inhale, Hold, Exhale, Hold');
  const inhale = widthAt(s, 0, 3800), hold1 = widthAt(s, 4500, 7800), exhale = widthAt(s, 8200, 11800);
  check(Math.max(...inhale) - Math.min(...inhale) > 30, 'circle grows during inhale: ' + Math.min(...inhale) + ' to ' + Math.max(...inhale));
  check(Math.max(...hold1) - Math.min(...hold1) < 2, 'circle holds its size during hold: ' + hold1[0]);
  check(exhale[0] - exhale[exhale.length - 1] > 30, 'circle shrinks during exhale: ' + exhale[0] + ' to ' + exhale[exhale.length - 1]);
  check(new Set(s.map(x => x.count)).size >= 4, 'per-phase countdown changes: ' + [...new Set(s.map(x => x.count))].join(','));
  check(/^Cycle 1 of \d+$/.test(await page.textContent('#breathing-cycle')), 'cycle counter: ' + await page.textContent('#breathing-cycle'));
  check(/\d+:\d\d left/.test(await page.textContent('#timer-display')), 'remaining time shown');
  check(Number(await page.getAttribute('#breathing-progress', 'value')) > 0, 'progress element advances');
  // Pause freezes the circle and the clock, resume continues.
  await page.click('#pause-btn');
  const a = await page.textContent('#timer-display'), wa = (await sample(page, 600))[0].w;
  await page.waitForTimeout(1500);
  const b = await page.textContent('#timer-display'), wb = (await sample(page, 300))[0].w;
  check(a === b && Math.abs(wa - wb) < 0.5, 'pause freezes clock and circle (' + a + ', ' + wa + ')');
  await page.click('#pause-btn');
  await page.waitForTimeout(1500);
  check(await page.textContent('#timer-display') !== b, 'resume restarts the clock');
  await page.click('#stop-btn');
  check((await page.textContent('#breathing-status')).includes('stopped'), 'stop announces the end');
  check(await page.isHidden('#save-prompt'), 'under a minute: no save prompt');
  check(page.errors.length === 0, 'no console errors ' + page.errors.join('|'));
  await browser.close();
}

// 2. Reduced motion: phases and countdown still run, toggle visible and off, then turned on.
{
  const { browser, page } = await openGuide('light', 'reduce');
  const tog = page.locator('#animated-toggle');
  check(await page.locator('.switch').isVisible() && !(await tog.isChecked()), 'toggle visible and off under reduced motion');
  await page.locator('#breathing-root').screenshot({ path: SHOTS + '/breathing-light-reduced.png' });
  await page.click('#start-btn');
  const s = await sample(page, 3000);
  check(order(s)[0] === 'Inhale' && new Set(s.map(x => x.count)).size >= 4, 'reduced: word and countdown run');
  check(Math.max(...s.map(x => x.w)) - Math.min(...widthAt(s, 300, 3000)) < 2, 'reduced: circle jumps once, no in-between sizes');
  await page.click('#stop-btn');
  await page.locator('.switch').click();
  check(await tog.isChecked(), 'toggle turned on');
  await page.click('#start-btn');
  const t = await sample(page, 3500);
  check(Math.max(...t.map(x => x.w)) - Math.min(...t.map(x => x.w)) > 30 && new Set(t.map(x => x.w)).size > 6, 'after turning on, the circle animates smoothly');
  await page.click('#stop-btn');
  await page.reload();
  check(await page.locator('#animated-toggle').isChecked(), 'choice remembered after reload');
  await browser.close();
}

// 3. Screenshots, light and dark, and the landing helpline card.
for (const scheme of ['light', 'dark']) {
  const { browser, page } = await openGuide(scheme, 'no-preference');
  await page.click('#start-btn');
  await page.waitForTimeout(2500);
  await page.locator('#breathing-root').screenshot({ path: SHOTS + `/breathing-${scheme}-running.png` });
  await browser.close();
  const g = await launch(scheme, 'no-preference');
  await g.page.goto(B + '/');
  if (await g.page.getByRole('button', { name: 'Essential only' }).isVisible()) await g.page.getByRole('button', { name: 'Essential only' }).click();
  const box = await g.page.locator('.home-help').boundingBox();
  if (scheme === 'light') check(box.width <= 280 && box.height <= 200, `landing helpline card compact: ${Math.round(box.width)}x${Math.round(box.height)}`);
  const links = await g.page.locator('.home-help a[href^="tel:"]').evaluateAll(a => a.map(x => x.getAttribute('href')));
  check(links.length === 3, 'three tel links: ' + links.join(' '));
  await g.page.screenshot({ path: SHOTS + `/landing-${scheme}.png` });
  await g.browser.close();
}
console.log(failed ? failed + ' FAILED' : 'ALL PASSED');
process.exit(failed ? 1 : 0);
