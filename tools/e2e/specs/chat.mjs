// Chat starters: each is a real turn (user bubble, then reply), Print/Copy exist, print media hides the input.
import { launch, login, B } from '../lib.mjs';
const SHOT = process.env.SHOTS || '.';
const { browser, page } = await launch('light', process.env.REDUCED || 'no-preference');
let failed = 0;
const check = (name, ok, extra = '') => { console.log(ok ? 'PASS' : 'FAIL', name, extra); if (!ok) failed++; };

await login(page, 'demo.patient@example.com');
await page.goto(B + '/chat', { waitUntil: 'networkidle' });
const buttons = await page.$$('[data-template-id]');
check('starter buttons rendered', buttons.length >= 3 && buttons.length <= 6, String(buttons.length));

for (let i = 0; i < buttons.length; i++) {
  const btn = page.locator('[data-template-id]').nth(i);
  const text = await btn.getAttribute('data-template-text');
  const userBefore = await page.locator('.msg-user').count();
  const botBefore = await page.locator('.msg-bot:not(.msg-pending)').count();
  const t0 = Date.now();
  await btn.click();
  // user bubble appears immediately, with the exact template text
  await page.waitForFunction(n => document.querySelectorAll('.msg-user').length > n, userBefore, { timeout: 1500 });
  const bubble = await page.locator('.msg-user .msg-text').last().textContent();
  check(`user bubble ${i}`, bubble === text, bubble);
  // reply bubble follows
  await page.waitForFunction(n => document.querySelectorAll('.msg-bot:not(.msg-pending)').length > n, botBefore, { timeout: 15000 });
  const reply = (await page.locator('.msg-bot .msg-text').last().textContent()) || '';
  check(`reply bubble ${i}`, reply.length > 40, `${Date.now() - t0}ms`);
  check(`pending gone ${i}`, (await page.locator('.msg-pending').count()) === 0);
  check(`copy/print buttons ${i}`, (await page.locator('.msg-bot').last().locator('.msg-actions button').count()) === 2);
  const note = await page.locator('.msg-bot').last().locator('.msg-note').allTextContents();
  console.log('   note:', note.join('|') || '(none)');
}
const bottom = await page.evaluate(() => { const l = document.getElementById('chat-messages'); return l.scrollHeight - l.scrollTop - l.clientHeight; });
check('scrolled to newest', bottom < 4, String(bottom));
await page.screenshot({ path: SHOT + '/chat-screen.png', fullPage: true });

// free text still works (fallback or AI), as a normal turn
await page.fill('#chat-input', 'I feel a bit tired today.');
await page.keyboard.press('Enter');
await page.waitForFunction(() => !document.querySelector('.msg-pending') && !document.getElementById('chat-input').disabled, null, { timeout: 15000 });
console.log('   free text turn:', JSON.stringify(await page.locator('.msg').allInnerTexts().then(a => a.slice(-3).map(t => t.slice(0, 70)))));
check('free text reply', (await page.locator('.msg-bot:not(.msg-pending)').count()) > buttons.length + 1);

// print: only the conversation
await page.evaluate(() => { window.__printed = 0; window.print = () => { window.__printed++; }; });
await page.click('#chat-print-all');  // the button is on screen only; then check what the printed page would show
await page.emulateMedia({ media: 'print' });
check('print() called', (await page.evaluate(() => window.__printed)) === 1);
check('input hidden in print', !(await page.locator('#chat-input').isVisible()));
check('form hidden in print', !(await page.locator('#chat-form').isVisible()));
check('header hidden in print', !(await page.locator('.site-header').isVisible()));
check('print head shown', await page.locator('#chat-print-head').isVisible());
check('messages shown in print', (await page.locator('.msg-user').first().isVisible()));
check('disclaimer in print', /AI-generated, not advice/.test(await page.locator('#chat-print-head').textContent()));
await page.screenshot({ path: SHOT + '/chat-print.png', fullPage: true });
await page.emulateMedia({ media: 'screen' });
check('page errors', page.errors.length === 0, JSON.stringify(page.errors));
await browser.close();
process.exit(failed ? 1 : 0);
