// Follow-up tracker, score flags and reminders in a real browser. Needs a FRESH demo database (the spec acknowledges the demo crisis once): start `scripts/local_demo.py --reset --port 5205` with its own DATABASE_URL, run scratchpad seed for a second PHQ-9 on demo.patient, then: SHOTS=<dir> BASE=http://127.0.0.1:5205 node specs/followups.mjs
import { launch, login, B } from '../lib.mjs';
const S = process.env.SHOTS;
const check = (ok, msg) => { console.log((ok ? 'PASS ' : 'FAIL ') + msg); if (!ok) process.exitCode = 1; };
let first = true;
for (const scheme of ['light', 'dark']) {
  for (const [w, h, tag] of [[1280, 900, 'wide'], [390, 844, 'phone']]) {
    const { browser, page } = await launch(scheme);
    await page.setViewportSize({ width: w, height: h });
    await login(page, 'demo.provider@example.com', 'provider');
    await page.goto(B + '/provider/dashboard', { waitUntil: 'networkidle' });
    const essential = page.locator('button:has-text("Essential only")');
    if (await essential.count()) await essential.click();  // the cookie banner would cover the screenshots
    if (first) {  // acknowledge the demo crisis case once; the plan then exists for every later run
      const ack = page.locator('button:has-text("Acknowledge alert")').first();
      if (await ack.count() === 1) { await ack.click(); await page.waitForLoadState('networkidle'); console.log('PASS acknowledged the demo crisis alert'); }
      else console.log('NOTE alert already acknowledged by an earlier run');
    }
    const panel = page.locator('[data-fu-root]');
    check(await panel.locator('text=Demo Patient Two').count() >= 1, `${scheme} ${tag}: plan listed in the Follow-ups panel`);
    check(await panel.locator('text=Next 7 days').count() === 1, `${scheme} ${tag}: step due in 2 days is under "Next 7 days"`);
    await panel.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${S}/fu_panel_${scheme}_${tag}.png` });
    if (first) {
      await page.locator('[data-fu-done]').first().click();
      await page.selectOption('#fuOutcome', 'contacted_by_phone');
      await page.screenshot({ path: `${S}/fu_dialog_${scheme}_${tag}.png` });
      await page.click('#fuDoneSave');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1500);
      check(await page.locator('[data-fu-root] [data-fu-done]').count() >= 1, 'a step was marked done and the panel reloaded');
      first = false;
    } else {
      await page.locator('[data-fu-done]').first().click();
      await page.screenshot({ path: `${S}/fu_dialog_${scheme}_${tag}.png` });
      await page.click('#fuDoneCancel');
    }
    const flag = page.locator('#caseloadTable .fu-flag');
    check(await flag.count() >= 1, `${scheme} ${tag}: caseload shows a score flag: ${await flag.first().innerText()}`);
    await page.locator('#caseloadTable').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${S}/fu_caseload_${scheme}_${tag}.png` });
    await page.check('#caseloadFlagged');
    const visible = await page.locator('#caseloadTable tbody tr:not(.fu-flag-hidden)').count();
    check(visible >= 1 && visible < await page.locator('#caseloadTable tbody tr').count(), `${scheme} ${tag}: flag filter narrows the table to ${visible}`);
    await page.uncheck('#caseloadFlagged');
    const href = await page.locator('[data-fu-root] a[href*="wellness-report"]').first().getAttribute('href');
    await page.goto(B + href, { waitUntil: 'networkidle' });
    check(await page.locator('text=Follow-up 1').count() >= 1 && await page.locator('text=Done').count() >= 1, `${scheme} ${tag}: report timeline shows the done step`);
    await page.locator('#fu-timeline-heading').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${S}/fu_report_${scheme}_${tag}.png`, fullPage: false });
    await page.goto(B + '/provider/dashboard', { waitUntil: 'networkidle' });
    const flagged = await page.locator('#caseloadTable tr[data-flag="1"] a[href*="wellness-report"]').first().getAttribute('href');
    await page.goto(B + flagged, { waitUntil: 'networkidle' });
    check(await page.locator('svg.fu-spark polyline').count() >= 1 && await page.locator('text=Show PHQ-9 as a table').count() === 1, `${scheme} ${tag}: sparkline with a table alternative`);
    await page.locator('#fu-trend-heading').scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${S}/fu_trend_${scheme}_${tag}.png`, fullPage: false });
    const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(ov <= 0, `${scheme} ${tag}: no horizontal overflow (${ov}px)`);
    check(page.errors.length === 0, `${scheme} ${tag}: no console errors ${page.errors.join(' | ')}`);
    await browser.close();
  }
}
