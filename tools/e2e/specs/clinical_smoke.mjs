import { launch, login, B } from '../lib.mjs';
let failed = 0;
const run = async (label, scheme, email, role, paths, adminLogin = false) => {
  const { browser, page } = await launch(scheme);
  if (adminLogin) {
    await page.goto(B + '/admin/login');
    await page.fill('input[name=email]', email);
    await page.fill('input[name=password]', 'Demo@Pass2026');
    await page.click('form:has(input[name=password]) button[type=submit]');
    await page.waitForLoadState('networkidle');
  } else await login(page, email, role);
  console.log(`\n== ${label} landed on ${page.url().replace(B, '')}`);
  for (const p of paths) {
    page.errors.length = 0;
    const resp = await page.goto(B + p, { waitUntil: 'networkidle' }).catch(e => ({ status: () => 'ERR ' + e.message.slice(0, 40) }));
    const h1 = await page.$eval('h1', e => e.textContent.trim().slice(0, 40)).catch(() => '-');
    if (resp.status() !== 200 || page.errors.length) failed++;
    console.log(`  ${p.padEnd(30)} ${resp.status()}  h1="${h1}"  ${page.errors.length ? 'ERRORS: ' + page.errors.slice(0, 3).join(' | ') : ''}`);
  }
  await browser.close();
};
await run('ADMIN', 'light', 'demo.admin@example.com', 'admin', ['/admin/', '/admin/verification', '/admin/catalogue', '/admin/catalogue/new', '/admin/inventory', '/admin/inventory/batches', '/admin/inventory/receive', '/admin/dispensing', '/admin/reports', '/admin/audit', '/admin/annual-report', '/admin/messages', '/admin/staff'], true);
await run('DOCTOR', 'light', 'demo.doctor@example.com', 'provider', ['/provider/dashboard', '/provider/prescribe', '/provider/prescriptions', '/provider/analytics']);
await run('COUNSELLOR', 'light', 'demo.provider@example.com', 'provider', ['/provider/dashboard', '/provider/analytics', '/provider/ai-documentation']);
await run('PATIENT', 'light', 'demo.patient@example.com', 'patient', ['/patient/dashboard', '/patient/my-prescriptions', '/patient/schedule', '/account/data']);
console.log(failed ? failed + ' page(s) failed' : 'ALL PASSED');
process.exit(failed ? 1 : 0);
