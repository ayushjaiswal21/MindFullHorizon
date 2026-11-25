// Mood/sleep trend flags (utils/trend_flags.py) on the caseload and the wellness report.
// Needs demo.patient2 seeded with a step-change mood+sleep series (scratchpad/seed_trends.py), server on BASE.
import { launch, login, B } from '../lib.mjs';
const S = process.env.SHOTS;
const check = (ok, msg) => { console.log((ok ? 'PASS ' : 'FAIL ') + msg); if (!ok) process.exitCode = 1; };
for (const scheme of ['light', 'dark']) {
  for (const [w, h, tag] of [[1280, 900, 'wide'], [390, 844, 'phone']]) {
    const { browser, page } = await launch(scheme);
    await page.setViewportSize({ width: w, height: h });
    await login(page, 'demo.provider@example.com', 'provider');
    await page.goto(B + '/provider/dashboard', { waitUntil: 'networkidle' });
    const essential = page.locator('button:has-text("Essential only")');
    if (await essential.count()) await essential.click();
    const row = page.locator('#caseloadTable tr', { hasText: 'Demo Patient Two' });
    check(await row.locator('svg use[href*="#icon-mood"], svg use[href*="#icon-moon"]').count() >= 1,
      `${scheme} ${tag}: caseload row shows a mood/sleep trend icon`);
    check(await row.locator('text=down since').count() >= 1,
      `${scheme} ${tag}: caseload row shows the trend flag text`);
    await row.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${S}/trend_caseload_${scheme}_${tag}.png` });
    const href = await row.locator('a[href*="wellness-report"]').first().getAttribute('href');
    await page.goto(B + href, { waitUntil: 'networkidle' });
    check(await page.locator('#trend-heading').count() === 1, `${scheme} ${tag}: report has the trend section`);
    check(await page.locator('svg.fu-spark').count() >= 2, `${scheme} ${tag}: mood and sleep sparklines present`);
    check(await page.locator('text=Show mood as a table').count() === 1 && await page.locator('text=Show sleep as a table').count() === 1,
      `${scheme} ${tag}: text-table alternative for both sparklines`);
    check(await page.locator('text=down since').count() >= 1, `${scheme} ${tag}: report shows the trend flag`);
    await page.locator('#trend-heading').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${S}/trend_report_${scheme}_${tag}.png`, fullPage: false });
    const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(ov <= 0, `${scheme} ${tag}: no horizontal overflow (${ov}px)`);
    check(page.errors.length === 0, `${scheme} ${tag}: no console errors ${page.errors.join(' | ')}`);
    await browser.close();
  }
}
