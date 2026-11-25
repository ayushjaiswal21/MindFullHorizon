// AI personal-text policy, flag OFF (the default): chat answers from saved answers and the safety check, the disclosure
// says so, the starter answers show, free text gets the fixed reply, and the dashboard shows the labelled tip card.
// Run against a server started WITHOUT AI_SEND_PERSONAL_TEXT:  BASE=http://127.0.0.1:5206 SHOTS=<dir> node specs/ai_policy.mjs
import { launch, login, B } from '../lib.mjs';
const SHOT = process.env.SHOTS || '.';
let failed = 0;
const check = (name, ok, extra = '') => { console.log(ok ? 'PASS' : 'FAIL', name, extra); if (!ok) failed++; };

for (const scheme of ['light', 'dark']) {
  const { browser, page } = await launch(scheme);
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, 'demo.patient@example.com');

  await page.goto(B + '/chat', { waitUntil: 'networkidle' });
  const lead = (await page.locator('.page-header .lead').textContent()) || '';
  check(`${scheme}: disclosure sentence`, lead.includes('Anya replies from saved answers and a safety check; no AI model reads what you write'), lead.slice(0, 60));
  const page_text = await page.locator('body').innerText();
  check(`${scheme}: no "AI assistant" claim`, !/Anya is an AI assistant|I am an AI, not a therapist/.test(page_text));
  check(`${scheme}: says automated assistant`, /automated assistant/.test(page_text));

  const starters = page.locator('[data-template-id]');
  check(`${scheme}: starters rendered`, (await starters.count()) >= 3);
  const botBefore = await page.locator('.msg-bot:not(.msg-pending)').count();
  await starters.first().click();
  await page.locator('.msg-bot:not(.msg-pending)').nth(botBefore).waitFor({ timeout: 15000 });  // locator waits: the page CSP bans eval
  const starterReply = (await page.locator('.msg-bot .msg-text').last().textContent()) || '';
  check(`${scheme}: starter gets a saved answer`, starterReply.length > 60, starterReply.slice(0, 50));

  await page.fill('#chat-input', 'I feel a bit tired and nervous about my exam.');
  await page.keyboard.press('Enter');
  await page.locator('.msg-pending').waitFor({ state: 'detached', timeout: 15000 });
  const free = (await page.locator('.msg-bot .msg-text').last().textContent()) || '';
  check(`${scheme}: free text gets the fixed reply`, free.includes('no AI model reads what you write') && free.includes('14416'), free.slice(0, 70));
  check(`${scheme}: no unavailable notice`, !/temporarily unavailable/.test(await page.locator('body').innerText()));
  await page.screenshot({ path: `${SHOT}/ai-policy-chat-${scheme}.png`, fullPage: true });

  await page.fill('#chat-input', 'I want to kill myself');
  await page.keyboard.press('Enter');
  await page.locator('.msg-pending').waitFor({ state: 'detached', timeout: 15000 });
  const crisis = await page.locator('body').innerText();
  check(`${scheme}: crisis floor still answers`, crisis.includes('Tele-MANAS') && crisis.includes('14416'));

  await page.goto(B + '/patient/dashboard', { waitUntil: 'networkidle' });
  const card = page.locator('#tip-card');
  check(`${scheme}: tip card visible`, await card.isVisible());
  check(`${scheme}: tip label`, ((await card.innerText()) || '').includes('General tip, not advice for you.'));
  check(`${scheme}: tip text present`, ((await card.locator('[data-tip-text]').innerText()) || '').length > 20);
  await card.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SHOT}/ai-policy-dashboard-${scheme}.png`, fullPage: true });
  check(`${scheme}: no horizontal scroll`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));

  await page.goto(B + '/ai', { waitUntil: 'networkidle' });
  check(`${scheme}: /ai explainer`, (await page.locator('article').innerText()).includes('no AI model reads what you write'));
  console.log('  errors:', JSON.stringify(page.errors));
  check(`${scheme}: no page errors`, page.errors.filter(e => !/favicon/.test(e)).length === 0);
  await browser.close();
}
console.log(failed ? `${failed} FAILED` : 'ALL PASSED');
process.exit(failed ? 1 : 0);
