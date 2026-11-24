// Chat failure paths: Retry bubble, 12 s UI timeout, 429 budget reply, crisis banner. Run with BASE set.
import { launch, login, B } from '../lib.mjs';
const { browser, page } = await launch('light', 'reduce');
let failed = 0;
const check = (n, ok, x = '') => { console.log(ok ? 'PASS' : 'FAIL', n, x); if (!ok) failed++; };
await login(page, 'demo.patient@example.com');
await page.goto(B + '/chat', { waitUntil: 'networkidle' });

// 1. failed template request: user bubble stays, error bubble with Retry, Retry gives the reply without a 2nd user bubble
await page.route('**/api/chat/template', r => r.abort());
await page.locator('[data-template-id]').first().click();
await page.waitForSelector('.msg-system button:has-text("Retry")');
check('error bubble + Retry', (await page.locator('.msg-user').count()) === 1);
await page.unroute('**/api/chat/template');
await page.click('.msg-system button:has-text("Retry")');
await page.waitForSelector('.msg-bot .msg-actions');
check('retry shows reply, one user bubble', (await page.locator('.msg-user').count()) === 1 && (await page.locator('.msg-system').count()) === 0);

// 2. 12 s UI timeout on free text
await page.route('**/api/chat', async r => { await new Promise(res => setTimeout(res, 14000)); r.abort().catch(() => {}); });
await page.fill('#chat-input', 'hello there'); await page.keyboard.press('Enter');
check('pending indicator shown', await page.locator('.msg-pending').isVisible());
const t0 = Date.now();
await page.waitForSelector('.msg-system button:has-text("Retry")', { timeout: 16000 });
const dt = Date.now() - t0;
check('timeout near 12 s', dt > 11000 && dt < 13500, dt + 'ms');
check('timeout text', /taking longer/.test(await page.locator('.msg-system').last().textContent()));
await page.unroute('**/api/chat');

// 3. 429 budget reply shows reply text and helplines from payload
await page.route('**/api/chat', r => r.fulfill({ status: 429, contentType: 'application/json', body: JSON.stringify({ ok: false, error: 'Limit reached MARK', reply: 'Limit reached MARK', rate_limited: true, retry_after: 30, helplines: [{ name: 'Test line', number: '555', tel: '555', hours: '24x7' }] }) }));
await page.fill('#chat-input', 'again'); await page.keyboard.press('Enter');
await page.waitForSelector('text=Limit reached MARK');
check('429 reply + helplines', /Test line: 555/.test(await page.locator('#chat-notice').textContent()));
await page.unroute('**/api/chat');

// 4. crisis text: fixed reply and banner with the real helplines
await page.fill('#chat-input', 'i want to kill myself'); await page.keyboard.press('Enter');
await page.waitForSelector('#chat-banner:not([hidden])');
const banner = await page.locator('#chat-banner').textContent();
check('crisis banner has helplines', /14416/.test(banner) && /112/.test(banner));
check('crisis reply shown', /You matter/.test(await page.locator('.msg-bot').last().textContent()));
check('starters removed after crisis', (await page.locator('#chat-starters').count()) === 0);
check('no script errors', page.errors.filter(e => e.startsWith('PAGEERROR')).length === 0, JSON.stringify(page.errors));  // failed requests are induced above
await browser.close();
process.exit(failed ? 1 : 0);
