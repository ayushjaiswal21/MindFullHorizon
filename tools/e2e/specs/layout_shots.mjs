// Screenshots at phone width for eyeballing: OUT=<dir> WIDTH=390 node specs/layout_shots.mjs [name ...]
import { mkdirSync } from 'node:fs';
import { launch, login, B } from '../lib.mjs';

const OUT = process.env.OUT || '.';
const W = Number(process.env.WIDTH || 390);
mkdirSync(OUT, { recursive: true });
const SHOTS = {
  landing: ['guest', '/'], login: ['guest', '/login'], signup: ['guest', '/signup'],
  dashboard: ['patient', '/patient/dashboard'], assessment: ['patient', '/patient/assessment'], chat: ['patient', '/chat'],
  breathing: ['patient', '/patient/breathing'], schedule: ['patient', '/patient/schedule'], journal: ['patient', '/patient/journal'],
  profile: ['patient', '/profile'], provider: ['counsellor', '/provider/dashboard'], prescribe: ['doctor', '/provider/prescribe'],
  admin: ['admin', '/admin/'], catalogue: ['admin', '/admin/catalogue'],
  progress: ['patient', '/patient/progress'], goals: ['patient', '/patient/goals'], yoga: ['patient', '/patient/yoga'], sleep: ['patient', '/patient/sleep'],
  safetyplan: ['patient', '/patient/safety-plan/edit'], rxdetail: ['patient', '/patient/prescriptions/1'], telehealth: ['patient', '/telehealth'],
  analytics: ['counsellor', '/provider/analytics'], session: ['counsellor', '/telehealth_session/1'], report: ['counsellor', '/provider/wellness-report/1'],
  inventory: ['admin', '/admin/inventory'], blog: ['guest', '/blog/'], contact: ['guest', '/contact'], privacy: ['guest', '/privacy'],
};
const ACCOUNTS = { patient: ['demo.patient@example.com', 'patient'], counsellor: ['demo.provider@example.com', 'provider'], doctor: ['demo.doctor@example.com', 'provider'] };
const want = process.argv.slice(2);
for (const scheme of ['light', 'dark']) {
  for (const role of ['guest', 'patient', 'counsellor', 'doctor', 'admin']) {
    const names = Object.keys(SHOTS).filter((n) => SHOTS[n][0] === role && (!want.length || want.includes(n)));
    if (!names.length) continue;
    const { browser, page } = await launch(scheme);
    await page.setViewportSize({ width: W, height: 844 });
    if (role === 'admin') {
      await page.goto(B + '/admin/login');
      await page.fill('input[name=email]', 'demo.admin@example.com');
      await page.fill('input[name=password]', 'Demo@Pass2026');
      await page.click('form:has(input[name=password]) button[type=submit]');
      await page.waitForLoadState('networkidle');
    } else if (role !== 'guest') await login(page, ...ACCOUNTS[role]);
    for (const n of names) {
      await page.goto(B + SHOTS[n][1], { waitUntil: 'networkidle' });
      if (process.env.BANNER !== '1') { const b = await page.$('[data-consent="essential"]'); if (b && await b.isVisible()) await b.click(); }
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${OUT}/${n}-${W}-${scheme}.png`, fullPage: process.env.FULL === '1' });
      console.log('shot', n, scheme);
    }
    await browser.close();
  }
}
