import { launch, login, B } from '../lib.mjs';
const SC = process.env.SHOTS || '.';
async function run(kind, scheme, reduced, vw) {
  const { browser, ctx, page } = await launch(scheme, reduced);
  if (vw) await page.setViewportSize({ width: vw, height: 800 });
  await login(page, 'demo.patient@example.com');
  await page.goto(B + '/patient/assessment'); await page.waitForLoadState('networkidle');
  await page.click(`.start-assessment-btn[data-assessment-type="${kind}"]`);
  await page.waitForSelector('#assessment-form:not([hidden])', { timeout: 4000 });
  const n = kind === 'PHQ-9' ? 9 : 7;
  console.log(kind, scheme, reduced, vw || 1280, 'form visible, first:', (await page.textContent('#assessment-question')).slice(0, 50));
  // empty next shows error
  await page.click('#nextBtn');
  console.log(' error on empty:', await page.textContent('#assessment-error'));
  for (let i = 0; i < n; i++) {
    if (i % 2 === 0) await page.keyboard.press('2'); else await page.click('#assessment-options label >> nth=1');
    if (i === 2) { await page.click('#prevBtn'); await page.click('#nextBtn'); console.log(' back/next kept answer:', await page.isChecked('#assessment-options input >> nth=1')); }
    if (i === 0 && kind==='PHQ-9') await page.screenshot({ path: `${SC}/u1_${kind}_${scheme}_${vw||1280}.png` });
    if (i < n - 1) await page.click('#nextBtn');
  }
  await page.click('#nextBtn');
  await page.waitForSelector('#assessment-result:not([hidden])', { timeout: 8000 });
  console.log(' result:', await page.textContent('#result-score'), await page.textContent('#result-max'), await page.textContent('#result-band'), '|', (await page.textContent('#result-explain')).slice(0, 50));
  console.log(' crisis banner:', await page.isVisible('#crisis-card'));
  await page.screenshot({ path: `${SC}/u1_${kind}_result_${scheme}_${vw||1280}.png`, fullPage: true });
  await page.reload(); await page.waitForLoadState('networkidle');
  console.log(' history rows:', await page.$$eval('#assessmentHistory tr', r => r.length), await page.$$eval('#assessmentHistory tr:first-child td', t => t.map(x => x.textContent.trim()).join(' / ')));
  console.log(' errors', page.errors);
  await browser.close();
}
await run('PHQ-9', 'light', 'no-preference');
await run('GAD-7', 'dark', 'reduce');
await run('PHQ-9', 'light', 'no-preference', 390);
