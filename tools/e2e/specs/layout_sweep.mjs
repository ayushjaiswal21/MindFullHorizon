// Layout sweep: every reachable GET page of every role, 7 widths x 2 colour schemes.
//   cd tools/e2e && DATABASE_URL=sqlite:///.../demo_x.db PYTHON=python BASE=http://127.0.0.1:5201 node specs/layout_sweep.mjs
// Env: BLOCK=regex of request URLs to abort (for before/after comparisons), ONLY=/patient (path prefix filter), ROLES=guest,patient, WIDTHS=360,390, SCHEMES=light, JSON=out.json, VERBOSE=1.
// Prints one row per page with problems and exits 1 when any page overflows horizontally or logs errors.
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch, B } from '../lib.mjs';
import { probe } from '../layout_probe.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const env = process.env;
const WIDTHS = (env.WIDTHS || '360,390,768,1024,1280,1440,1920').split(',').map(Number);
const SCHEMES = (env.SCHEMES || 'light,dark').split(',');
const PW = 'Demo@Pass2026';
const ROLES = [
  { name: 'guest' },
  { name: 'patient', email: 'demo.patient@example.com', role: 'patient' },
  { name: 'patient2', email: 'demo.patient2@example.com', role: 'patient' },
  { name: 'counsellor', email: 'demo.provider@example.com', role: 'provider' },
  { name: 'doctor', email: 'demo.doctor@example.com', role: 'provider' },
  { name: 'admin', email: 'demo.admin@example.com', admin: true },
].filter((r) => !env.ROLES || env.ROLES.split(',').includes(r.name));

const out = execFileSync(env.PYTHON || 'python', [resolve(root, 'tools/e2e/list_routes.py')], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
const rules = [], params = [];
for (const line of out.split('\n')) {
  const [a, b] = line.trim().split('\t');
  if (a === 'PARAM') params.push(b); else if (a && a.startsWith('/') && b) rules.push(a);
}
const SKIP = /^\/(api|health|ready|robots|sitemap|favicon|login\/google|audio|static)|\/api\/|\.(csv|txt|xml)$|^\/admin\/inventory\/(template|stock)/;
const guestExtras = ['/search?q=anxiety', '/blog/', '/__no_such_page__'];
const candidates = [...new Set([...rules.filter((p) => !SKIP.test(p)), ...params, ...guestExtras])]
  .filter((p) => !env.ONLY || p.startsWith(env.ONLY));

async function signIn(page, r) {
  if (!r.email) return;
  if (r.admin) {
    await page.goto(B + '/admin/login');
    await page.fill('input[name=email]', r.email);
    await page.fill('input[name=password]', PW);
    await page.click('form:has(input[name=password]) button[type=submit]');
    await page.waitForLoadState('networkidle');
  } else {
    await page.goto(B + '/login');
    await page.fill('input[name=email]', r.email);
    await page.fill('input[name=password]', PW);
    await page.selectOption('select[name=role]', r.role);
    await page.click('form:has(input[name=password]) button[type=submit]');
    await page.waitForLoadState('networkidle');
  }
}

async function reachable(ctx, path) {
  const res = await ctx.request.get(B + path, { maxRedirects: 0, failOnStatusCode: false });
  return (res.status() === 200 && /text\/html/.test(res.headers()['content-type'] || '')) || path === '/__no_such_page__';
}

const rows = []; // {role, path, scheme, width, ...probe}
const guestPages = new Set();
for (const scheme of SCHEMES) {
  for (const r of ROLES) {
    const { browser, ctx, page } = await launch(scheme);
    if (env.BLOCK) await ctx.route(new RegExp(env.BLOCK), (route) => route.abort());
    await signIn(page, r);
    let pages = [];
    for (const p of candidates) {
      if (!(await reachable(ctx, p))) continue;
      if (r.name === 'guest') guestPages.add(p);
      else if (guestPages.has(p) && r.name !== 'patient') continue; // public pages: guest and patient shell only
      pages.push(p);
    }
    let first = true;
    for (const p of pages) {
      page.errors.length = 0;
      let status = 0;
      try { status = (await page.goto(B + p, { waitUntil: 'networkidle', timeout: 20000 })).status(); } catch (e) { rows.push({ role: r.name, path: p, scheme, width: 0, err: 'NAV ' + e.message.slice(0, 60) }); continue; }
      if (first && r.name !== 'guest') { first = false; }
      const banner = await page.$('#consent-banner:not([hidden])');
      const errors = page.errors.filter((m) => !(p === '/__no_such_page__' && /404/.test(m)));
      for (const w of WIDTHS) {
        await page.setViewportSize({ width: w, height: w <= 480 ? 800 : 900 });
        const m = await page.evaluate(probe, { touch: w <= 768 });
        rows.push({ role: r.name, path: p, scheme, width: w, status, banner: !!banner, ...m, err: w === WIDTHS[0] ? errors.join(' | ') : '' });
      }
      if (banner) { // dismiss once, then the rest of the sweep sees the page the way a returning user does
        const btn = await page.$('[data-consent="essential"]');
        if (btn) await btn.click().catch(() => {});
      }
    }
    await browser.close();
    console.error(`[${scheme}] ${r.name}: ${pages.length} pages`);
  }
}

// aggregate per role+path
const agg = new Map();
for (const x of rows) {
  const k = x.role + ' ' + x.path;
  const a = agg.get(k) || { role: x.role, path: x.path, overflow: 0, ow: '', first: '', tap: new Set(), clip: new Set(), imgs: new Set(), cover: 0, coverW: '', err: new Set(), bad: x.status && x.status !== 200 && x.path !== '/__no_such_page__' };
  if (x.overflow > a.overflow) { a.overflow = x.overflow; a.ow = x.width + (x.scheme === 'dark' ? 'd' : ''); a.first = x.first; }
  (x.tap || []).forEach((t) => a.tap.add(x.width + ': ' + t));
  (x.clip || []).forEach((t) => a.clip.add(t));
  (x.imgs || []).forEach((t) => a.imgs.add(t));
  if ((x.cover || 0) > a.cover) { a.cover = x.cover; a.coverW = x.width + ' ' + x.coverBy; }
  if (x.err) a.err.add(x.err);
  agg.set(k, a);
}
const list = [...agg.values()];
const tapKeys = (a) => new Set([...a.tap].map((t) => t.replace(/^\d+: /, '')));
let nOver = 0, nTap = 0, nErr = 0, nClip = 0, nCover = 0, nImg = 0;
const trunc = (s, n) => (s.length > n ? s.slice(0, n - 1) + '~' : s);
console.log('role       path                                   ovf(px@w)  tap  clip  img  cover%  err');
for (const a of list) {
  const bad = a.overflow > 0, tapN = tapKeys(a).size;
  if (bad) nOver++; if (tapN) nTap++; if (a.err.size || a.bad) nErr++; if (a.clip.size) nClip++; if (a.cover > 40) nCover++; if (a.imgs.size) nImg++;
  if (env.VERBOSE || bad || tapN || a.err.size || a.clip.size || a.cover > 40 || a.imgs.size || a.bad) {
    console.log(`${a.role.padEnd(10)} ${trunc(a.path, 38).padEnd(38)} ${(a.overflow ? a.overflow + '@' + a.ow : '-').padEnd(10)} ${String(tapN || '-').padEnd(4)} ${String(a.clip.size || '-').padEnd(5)} ${String(a.imgs.size || '-').padEnd(4)} ${String(a.cover > 40 ? a.cover : '-').padEnd(7)} ${a.err.size || a.bad ? 'ERR' : '-'}`);
    if (env.DETAIL) {
      if (a.first) console.log('    first overflow:', a.first);
      [...a.err].forEach((e) => console.log('    error:', trunc(e, 200)));
      [...tapKeys(a)].slice(0, 6).forEach((t) => console.log('    tap:', t));
      [...a.clip].slice(0, 3).forEach((t) => console.log('    clip:', t));
      if (a.cover > 40) console.log('    cover:', a.coverW);
    }
  }
}
console.log(`\nSummary: ${list.length} role-pages x ${WIDTHS.length} widths x ${SCHEMES.length} schemes. overflow ${nOver}, tap targets ${nTap}, clipped text ${nClip}, images without size ${nImg}, covering ${nCover}, errors ${nErr}`);
if (env.JSON) writeFileSync(env.JSON, JSON.stringify(rows));
process.exit(nOver || nErr ? 1 : 0);
