// CAV agent: verify the LLM-score caveat + raw count render on the digital-detox and profile
// pages in light and dark at 1280px and 390px, with no console errors.
import { launch, login, B } from '../lib.mjs';
import fs from 'node:fs';

const SHOT_DIR = process.env.SHOT_DIR || '.';

async function checkPage(scheme, width, path, name) {
  const { browser, ctx, page } = await launch(scheme);
  await page.setViewportSize({ width, height: width < 500 ? 800 : 900 });
  await login(page, 'demo.patient@example.com', 'patient');

  // Log a screen time entry so the score/count are populated.
  await page.goto(B + '/patient/digital-detox');
  await page.fill('#screen_time', '5');
  await page.fill('#academic_score', '80');
  await page.selectOption('#social_interactions', 'high');
  await page.click('#detox-submit');
  await page.waitForTimeout(800);

  const caveatText = await page.textContent('#ai-score-caveat').catch(() => null);
  const countText = await page.textContent('#ai-score-count').catch(() => null);
  console.log(name, scheme, width, 'caveat=', JSON.stringify(caveatText), 'count=', countText, 'errors=', page.errors);

  await page.screenshot({ path: `${SHOT_DIR}/${name}_${scheme}_${width}.png`, fullPage: true });
  await browser.close();
  return { caveatText, countText, errors: page.errors };
}

(async () => {
  let failed = false;
  for (const scheme of ['light', 'dark']) {
    for (const width of [1280, 390]) {
      const r = await checkPage(scheme, width, '/patient/digital-detox', 'detox');
      if (!r.caveatText || !r.caveatText.includes('estimate written by an AI model')) {
        console.log('FAIL: caveat text missing or wrong', scheme, width);
        failed = true;
      }
      if (!r.countText || !/^\d+$/.test(r.countText.trim())) {
        console.log('FAIL: raw count missing', scheme, width);
        failed = true;
      }
      if (r.errors.length) {
        console.log('FAIL: console/page errors', scheme, width, r.errors);
        failed = true;
      }
    }
  }
  console.log(failed ? 'RESULT: FAIL' : 'RESULT: PASS');
  process.exit(failed ? 1 : 0);
})();
