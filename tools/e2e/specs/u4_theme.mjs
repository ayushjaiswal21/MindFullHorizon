// Screenshots of key pages in both colour schemes into SHOTS dir (u4 colour theme check).
import { launch, login, B } from '../lib.mjs';
const OUT = process.env.SHOTS;
const pages = [
  ['landing', '/', null], ['login', '/login', null], ['signup', '/signup', null], ['faq', '/faq', null], ['404', '/nope-404', null],
  ['dash', '/patient/dashboard', 'patient'], ['assess', '/patient/assessment', 'patient'], ['chat', '/chat', 'patient'],
  ['breathing', '/patient/breathing', 'patient'], ['schedule', '/patient/schedule', 'patient'], ['profile', '/profile', 'patient'],
  ['provider', '/provider/dashboard', 'provider'],
];
for (const scheme of ['light', 'dark']) {
  for (const role of [null, 'patient', 'provider']) {
    const { browser, page } = await launch(scheme);
    if (role) await login(page, role === 'patient' ? 'demo.patient@example.com' : 'demo.provider@example.com', role);
    for (const [name, path, r] of pages.filter(p => p[2] === role)) {
      const resp = await page.goto(B + path); await page.waitForLoadState('networkidle');
      await page.screenshot({ path: `${OUT}/${scheme}-${name}.png`, fullPage: true });
      console.log(scheme, name, resp.status(), page.url().replace(B, ''));
    }
    if (!role) { // error state: bad login, consent banner stays visible
      await page.goto(B + '/login'); await page.fill('input[name=email]', 'x@example.com'); await page.fill('input[name=password]', 'wrongwrong');
      await page.click('form:has(input[name=password]) button[type=submit]'); await page.waitForLoadState('networkidle');
      await page.screenshot({ path: `${OUT}/${scheme}-login-error.png`, fullPage: true });
    }
    console.log(scheme, role, 'errors:', page.errors.slice(0, 3));
    await browser.close();
  }
}
