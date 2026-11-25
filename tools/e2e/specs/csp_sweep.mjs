// CSP sweep: visit every GET page of the url map as each demo role with the policy ENFORCED, exercise the features
// that load extra resources, and report every securitypolicyviolation event and CSP console error. Exit 1 on any.
// Run from tools/e2e:  BASE=http://127.0.0.1:5203 DATABASE_URL=<same db as the server> PYTHON=<venv python> [ONLY=patient,admin] node specs/csp_sweep.mjs
import { chromium } from 'playwright-core';
import { execFileSync } from 'node:child_process';
import { B, login } from '../lib.mjs';

const ROOT = new URL('../../../', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const PYTHON = process.env.PYTHON || 'python';
const EDGE = process.env.EDGE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const paths = execFileSync(PYTHON, ['tools/e2e/csp_routes.py'], { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
  .split('\n').map(s => s.trim()).filter(s => s.startsWith('/'));
console.log(`pages in url map: ${paths.length}`);

const violations = [];
const seen = new Set();
const note = (who, where, v) => {
  const key = [v.directive, v.blocked, where].join('|');
  if (seen.has(key)) return;
  seen.add(key);
  violations.push({ who, where, ...v });
  console.log(`VIOLATION [${who}] ${where}: ${v.directive} blocked=${v.blocked} ${v.sample ? 'sample=' + v.sample : ''}`);
};

const ROLES = [
  { who: 'anon', email: null },
  { who: 'patient', email: 'demo.patient@example.com', role: 'patient' },
  { who: 'patient2', email: 'demo.patient2@example.com', role: 'patient' },
  { who: 'counsellor', email: 'demo.provider@example.com', role: 'provider' },
  { who: 'doctor', email: 'demo.doctor@example.com', role: 'provider' },
  { who: 'admin', email: 'demo.admin@example.com', role: 'admin' },
];

async function adminLogin(page, email) {
  await page.goto(B + '/admin/login');
  await page.fill('input[name=email]', email);
  await page.fill('input[name=password]', 'Demo@Pass2026');
  await page.click('form:has(input[name=password]) button[type=submit]');
  await page.waitForLoadState('networkidle');
}

async function open(role) {
  const browser = await chromium.launch({
    executablePath: EDGE, headless: true,
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ['microphone', 'camera'] });
  const page = await ctx.newPage();
  page.where = '(login)';
  await page.exposeFunction('__cspReport', v => note(role.who, page.where, v));
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', e => {
      window.__cspReport({ directive: e.effectiveDirective, blocked: e.blockedURI, sample: (e.sample || '').slice(0, 60), disposition: e.disposition });
    });
  });
  page.on('console', m => {
    if (m.type() === 'error' && /Content Security Policy|Refused to/i.test(m.text())) note(role.who, page.where, { directive: 'console', blocked: m.text().slice(0, 160) });
  });
  page.on('pageerror', e => { if (/Content Security|unsafe-eval/i.test(e.message)) note(role.who, page.where, { directive: 'pageerror', blocked: e.message.slice(0, 160) }); });
  return { browser, page };
}

async function settle(page) {
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(250);
}

async function visit(page, path) {
  page.where = path;
  const r = await page.goto(B + path, { waitUntil: 'load', timeout: 20000 }).catch(e => ({ status: () => 'ERR ' + e.message.slice(0, 60) }));
  await settle(page);
  return typeof r.status === 'function' ? r.status() : '?';
}

// Interactions: each one runs on its own page and swallows its own errors so one missing control cannot hide the rest.
async function step(page, name, fn) {
  try { await fn(); console.log('  ok   ' + name); } catch (e) { console.log('  skip ' + name + ' (' + e.message.split('\n')[0].slice(0, 90) + ')'); }
  await settle(page);
}

async function patientFeatures(page) {
  await step(page, 'consent banner, theme switch, menu', async () => {
    await visit(page, '/');
    const accept = page.locator('[data-consent=analytics]');
    if (await accept.isVisible()) await accept.click();
    await page.locator('[data-theme-toggle]').click();
    await page.locator('[data-theme-toggle]').click();
    await page.locator('[data-menu-group] > button').first().click();
  });
  await step(page, 'chat starter and free text', async () => {
    await visit(page, '/chat');
    await page.locator('[data-template-id]').first().click();
    // locator waits, not waitForFunction: Playwright's string eval would itself trip the policy
    await page.locator('.msg-bot:not(.msg-pending)').first().waitFor({ timeout: 15000 });
    await page.fill('#chat-input', 'I feel a bit tired today.');
    await page.keyboard.press('Enter');
    await page.locator('.msg-pending').waitFor({ state: 'detached', timeout: 15000 });
  });
  await step(page, 'breathing guide', async () => {
    await visit(page, '/patient/breathing');
    await page.click('#start-btn');
    await page.waitForTimeout(2500);
    await page.click('#pause-btn');
  });
  await step(page, 'yoga video facade', async () => {
    await visit(page, '/patient/yoga/videos');
    await page.locator('.video-facade').first().click();
    await page.waitForSelector('.video-frame iframe', { timeout: 5000 });
    await page.waitForTimeout(1500);
  });
  await step(page, 'goal modal', async () => {
    await visit(page, '/patient/goals');
    await page.getByRole('button', { name: /goal/i }).first().click();
    await page.waitForSelector('dialog[open]', { timeout: 3000 });
    await page.keyboard.press('Escape');
  });
  await step(page, 'mood check-in on dashboard', async () => {
    await visit(page, '/patient/dashboard');
    const radio = page.locator('input[name=mood_score], [data-mood]').first();
    if (await radio.count()) await radio.click({ force: true });
  });
  await step(page, 'telehealth page and socket', async () => {
    await visit(page, '/telehealth');
    await page.waitForTimeout(2500);
  });
  await step(page, 'music audio', async () => {
    await visit(page, '/music');
    await page.evaluate(() => { const a = document.getElementById('mood-audio'); if (a) { a.src = '/static/does-not-exist.mp3'; a.load(); } });
  });
  await step(page, 'voice log recorder (blob playback)', async () => {
    await visit(page, '/patient/voice-logs');
    const rec = page.getByRole('button', { name: /record|start/i }).first();
    await rec.click();
    await page.waitForTimeout(1500);
    await page.getByRole('button', { name: /stop/i }).first().click();
    await page.waitForTimeout(1000);
  });
  await step(page, 'assessment page, journal and charts', async () => {
    await visit(page, '/patient/progress');
    await visit(page, '/patient/journal');
  });
  await step(page, 'legacy socket chat (ai chat page)', async () => {
    await visit(page, '/ai');
    await page.waitForTimeout(1500);
  });
}

async function providerFeatures(page) {
  await step(page, 'provider dashboard socket, analytics charts', async () => {
    await visit(page, '/provider/dashboard');
    await page.waitForTimeout(1500);
    await visit(page, '/provider/analytics');
    await page.waitForTimeout(1500);
  });
  await step(page, 'dialogs on provider pages', async () => {
    await visit(page, '/provider/appointments');
    const b = page.locator('button[data-dialog], button[data-open]').first();
    if (await b.count()) await b.click();
  });
  await step(page, 'telehealth room for a patient', async () => {
    await visit(page, '/provider/telehealth/1');
    await page.waitForTimeout(2000);
  });
}

let exit = 0;
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);  // e.g. ONLY=patient,admin to split the run
for (const role of ROLES) {
  if (ONLY.length && !ONLY.includes(role.who)) continue;
  console.log(`== ${role.who}`);
  const { browser, page } = await open(role);
  if (role.email) { if (role.role === 'admin') await adminLogin(page, role.email); else await login(page, role.email, role.role); }
  const bad = [];
  for (const p of paths) {
    const status = await visit(page, p);
    if (!/^(200|30\d|40[134]|404)$/.test(String(status))) bad.push(`${p}:${status}`);
  }
  if (bad.length) console.log('  non-OK statuses (not CSP related unless 5xx):', bad.join(' '));
  if (role.who === 'patient') await patientFeatures(page);
  if (role.who === 'counsellor' || role.who === 'doctor') await providerFeatures(page);
  await browser.close();
}

console.log(`\nCSP violations: ${violations.length}`);
for (const v of violations) console.log(` - ${v.who} ${v.where} ${v.directive} ${v.blocked}`);
if (violations.length) exit = 1;
process.exit(exit);
