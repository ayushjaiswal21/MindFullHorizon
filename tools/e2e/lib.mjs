import { chromium } from 'playwright-core';
export const B = process.env.BASE || 'http://127.0.0.1:5000';
export async function launch(scheme='light', reduced='no-preference') {
  const browser = await chromium.launch({ executablePath: process.env.EDGE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: scheme, reducedMotion: reduced });
  const page = await ctx.newPage();
  page.errors = [];
  page.on('pageerror', e => page.errors.push('PAGEERROR ' + e.message));
  page.on('console', m => { if (m.type() === 'error') page.errors.push('CONSOLE ' + m.text().slice(0, 200)); });
  page.on('requestfailed', r => page.errors.push('REQFAIL ' + r.url().slice(0, 100)));
  return { browser, ctx, page };
}
export async function login(page, email, role = 'patient') {
  await page.goto(B + '/login');
  await page.fill('input[name=email]', email);
  await page.fill('input[name=password]', 'Demo@Pass2026');
  await page.selectOption('select[name=role]', role);
  await page.click('form:has(input[name=password]) button[type=submit]');
  await page.waitForLoadState('networkidle');
}
