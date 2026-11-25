import { launch, login, B } from '../lib.mjs';
const { browser, page } = await launch();
await login(page, 'demo.patient@example.com');
console.log('after login url', page.url());
// 1. assessment
await page.goto(B + '/patient/assessment'); await page.waitForLoadState('networkidle');
const btns = await page.$$eval('.start-assessment-btn', b => b.map(x => x.textContent.trim() + '|' + x.dataset.assessmentType));
console.log('assessment buttons', btns);
await page.click('.start-assessment-btn >> nth=0');
await page.waitForTimeout(1500);
const modalVisible = await page.isVisible('#assessmentModal').catch(() => false);
console.log('modal visible?', modalVisible, '| question:', (await page.textContent('#assessment-question').catch(()=>'')).slice(0,80));
let failed = modalVisible ? 0 : 1;
console.log('errors', page.errors);
// 3. progress timing
const t = Date.now(); await page.goto(B + '/patient/progress', { waitUntil: 'load' }); console.log('progress load ms', Date.now() - t);
const t2 = Date.now(); await page.waitForLoadState('networkidle'); console.log('progress networkidle extra ms', Date.now() - t2);
console.log('errors', page.errors);
if (page.errors.length) failed++;
await browser.close();
console.log(failed ? 'FAILED' : 'PASSED');
process.exit(failed ? 1 : 0);
