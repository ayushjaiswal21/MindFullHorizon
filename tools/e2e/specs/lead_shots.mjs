import { launch, login, B } from '../lib.mjs';
const S = process.env.SHOTS;
for (const scheme of ['light', 'dark']) {
  const { browser, page } = await launch(scheme);
  await page.goto(B + '/'); await page.waitForTimeout(500);
  await page.screenshot({ path: `${S}/L_landing_${scheme}.png`, fullPage: false });
  await login(page, 'demo.patient@example.com', 'patient');
  await page.goto(B + '/patient/dashboard', { waitUntil: 'networkidle' });
  await page.screenshot({ path: `${S}/L_dash_${scheme}.png`, fullPage: false });
  const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  console.log(scheme, 'dashboard horizontal overflow px:', ov);
  await browser.close();
}
