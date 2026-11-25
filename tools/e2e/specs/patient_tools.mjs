// Safety plan (create, print), grounding, sleep log (chart and table), reminders (pending state).
// Run: BASE=http://127.0.0.1:5204 SHOTS=<dir> node specs/patient_tools.mjs
import { launch, login, B } from '../lib.mjs';
import { mkdirSync } from 'node:fs';

const SHOTS = process.env.SHOTS || '.';
mkdirSync(SHOTS, { recursive: true });
let failed = 0;
const check = (ok, msg) => { console.log((ok ? 'PASS ' : 'FAIL ') + msg); if (!ok) failed++; };
const SECRET = 'Pause and text a friend';

async function run(scheme, width, height) {
  const tag = `${scheme}-${width}`;
  const { browser, page } = await launch(scheme);
  await page.setViewportSize({ width, height });
  await login(page, 'demo.patient@example.com');
  const essential = page.getByRole('button', { name: 'Essential only' });
  if (await essential.isVisible().catch(() => false)) await essential.click();
  const noOverflow = async (name) => check(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${tag} ${name}: no horizontal overflow`);

  // dashboard tools row
  await page.goto(B + '/patient/dashboard');
  check(await page.locator('#support-tools-heading').isVisible(), `${tag} dashboard shows Support tools`);
  await noOverflow('dashboard');

  // safety plan: create
  await page.goto(B + '/patient/safety-plan');
  if (await page.getByText('You have not made a safety plan yet').isVisible()) {
    await page.screenshot({ path: `${SHOTS}/plan-empty-${tag}.png`, fullPage: true });
    await page.click('text=Make my safety plan');
  } else {
    await page.goto(B + '/patient/safety-plan/edit');
  }
  await page.fill('#f-warning_signs', 'I stop eating and stay in my room.');
  await page.fill('#f-coping_alone', SECRET);
  await page.fill('#f-places_people', 'The library, my cousin');
  await page.fill('#pn-0', 'Asha (cousin)');
  await page.fill('#pp-0', '+91 98765 43210');
  await page.fill('#f-professionals', 'College counsellor, room 12');
  await page.fill('#f-safer_surroundings', 'Ask my warden to keep my medicines.');
  await page.screenshot({ path: `${SHOTS}/plan-edit-${tag}.png`, fullPage: true });
  await noOverflow('plan edit');
  await page.click('button:has-text("Save my plan")');
  await page.waitForLoadState('networkidle');
  check(await page.getByText(SECRET).isVisible(), `${tag} safety plan saved and shown`);
  check(await page.locator('a[href="tel:14416"]').count() > 0, `${tag} helplines shown on the plan`);
  await page.screenshot({ path: `${SHOTS}/plan-view-${tag}.png`, fullPage: true });
  await noOverflow('plan view');

  // print preview: emulate print media, chrome hidden, content kept
  await page.emulateMedia({ media: 'print' });
  const vis = async (sel) => page.locator(sel).first().isVisible().catch(() => false);
  check(!(await vis('.site-header')) && !(await vis('[data-print-page]')), `${tag} print hides header and buttons`);
  check(await page.getByText(SECRET).isVisible() && await vis('.sp-print-title'), `${tag} print keeps plan and title`);
  await page.screenshot({ path: `${SHOTS}/plan-print-${tag}.png`, fullPage: true });
  await page.pdf?.({ path: `${SHOTS}/plan-${tag}.pdf` }).catch(() => {});
  await page.emulateMedia({ media: 'screen' });

  // dashboard link text now says Open my safety plan
  await page.goto(B + '/patient/dashboard');
  check(await page.getByText('Open my safety plan').count() > 0, `${tag} dashboard link says Open my safety plan`);

  // grounding
  await page.goto(B + '/patient/grounding');
  check(await page.locator('#gr-next').isVisible(), `${tag} grounding Next visible`);
  for (let i = 1; i <= 5; i++) {
    check(await page.locator(`.gr-step[data-step="${i}"]`).isVisible(), `${tag} grounding step ${i} visible`);
    if (i === 1) await page.screenshot({ path: `${SHOTS}/grounding-${tag}.png`, fullPage: true });
    if (i === 3) { await page.keyboard.press('Tab'); await page.click('#gr-back'); await page.click('#gr-next'); }
    await page.click('#gr-next');
  }
  check(await page.getByText('You did it').isVisible(), `${tag} grounding end step`);
  await page.click('#gr-finish');
  await page.waitForSelector('#gr-again:not([hidden])');
  check((await page.locator('#gr-result').textContent()).length > 3, `${tag} grounding finish saved: ` + (await page.locator('#gr-result').textContent()));
  await page.screenshot({ path: `${SHOTS}/grounding-done-${tag}.png`, fullPage: true });
  await noOverflow('grounding');

  // sleep log
  await page.goto(B + '/patient/sleep');
  const saved = await page.getByText('Average:').isVisible().catch(() => false);
  if (!saved) {
    await page.fill('#bedtime', '23:30');
    await page.fill('#wake_time', '07:00');
    await page.check('input[name=quality][value="4"]');
    await page.fill('#note', 'Slept well after the walk');
    await page.click('button:has-text("Save entry")');
    await page.waitForLoadState('networkidle');
  }
  check(await page.locator('svg.sleep-chart rect.sc-bar').count() >= 1, `${tag} sleep chart has a bar`);
  check(await page.locator('table.table tbody tr').count() === 14, `${tag} sleep table has 14 rows`);
  check(await page.getByText('not a sleep score').isVisible(), `${tag} honest sleep wording`);
  await page.screenshot({ path: `${SHOTS}/sleep-${tag}.png`, fullPage: true });
  await noOverflow('sleep');

  // reminders
  await page.goto(B + '/patient/reminders');
  await page.selectOption('#frequency', 'daily');
  await page.selectOption('#hour', '20');
  if (!(await page.getByText('Waiting for your confirmation').isVisible().catch(() => false))) {
    await page.click('button:has-text("Turn on reminders")');
    await page.waitForLoadState('networkidle');
  }
  check(await page.getByText('Waiting for your confirmation').isVisible(), `${tag} reminders pending confirmation`);
  await page.screenshot({ path: `${SHOTS}/reminders-${tag}.png`, fullPage: true });
  await noOverflow('reminders');

  const errs = page.errors.filter(e => !/favicon|csp/i.test(e));
  check(errs.length === 0, `${tag} no console errors ${errs.join(' | ')}`);
  await browser.close();
}

for (const scheme of ['light', 'dark']) {
  await run(scheme, 390, 844);
  await run(scheme, 1280, 900);
}
console.log(failed ? `${failed} FAILED` : 'ALL PASSED');
process.exit(failed ? 1 : 0);
