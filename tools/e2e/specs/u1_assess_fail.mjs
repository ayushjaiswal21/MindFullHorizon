import { launch, login, B } from '../lib.mjs';
const { browser, page } = await launch();
await login(page, 'demo.patient@example.com');
await page.goto(B + '/patient/assessment'); await page.waitForLoadState('networkidle');
await page.route('**/patient/api/save-assessment', r => r.fulfill({ status: 500, contentType: 'application/json', body: '{"success":false}' }));
await page.click('.start-assessment-btn[data-assessment-type="PHQ-9"]');
await page.waitForSelector('#assessment-form:not([hidden])');
for (let i = 0; i < 9; i++) { await page.keyboard.press(i === 8 ? '3' : '1'); await page.click('#nextBtn'); }
await page.waitForTimeout(500);
console.log('crisis banner after failed save:', await page.isVisible('#crisis-card'), '| helplines:', await page.$$eval('#crisis-card li', l => l.map(x => x.textContent.trim().slice(0, 40))));
console.log('error text:', await page.textContent('#assessment-error'), '| form still visible:', await page.isVisible('#assessment-form'));
// Stop button with answers asks, then returns to picker
await page.unroute('**/patient/api/save-assessment');
console.log('errors', page.errors);
await browser.close();
