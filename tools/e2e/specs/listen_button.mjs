// Listen button (speechSynthesis): click on the chat page's saved answer and on the dashboard tip card, assert
// speechSynthesis.speak was called with the visible text, using only a local-only voice.
// Run: BASE=http://127.0.0.1:5306 SHOTS=<dir> node specs/listen_button.mjs
import { launch, login, B } from '../lib.mjs';
import { mkdirSync } from 'node:fs';

const SHOTS = process.env.SHOTS || '.';
mkdirSync(SHOTS, { recursive: true });
let failed = 0;
const check = (ok, msg) => { console.log((ok ? 'PASS ' : 'FAIL ') + msg); if (!ok) failed++; };

// Headless Chromium/Edge may expose zero or only remote voices, so stub speechSynthesis before any page script
// runs: one fake local-only voice, and record every speak() call (never actually speaking).
async function stubSpeech(page) {
  await page.addInitScript(() => {
    window.__speakCalls = [];
    const localVoice = { name: 'Test Local Voice', lang: 'en-IN', localService: true, default: true, voiceURI: 'test-local' };
    const remoteVoice = { name: 'Test Remote Voice', lang: 'en-IN', localService: false, default: false, voiceURI: 'test-remote' };
    const stub = {
      getVoices: () => [remoteVoice, localVoice],
      speak: (u) => { window.__speakCalls.push({ text: u.text, voice: u.voice ? { ...u.voice } : null }); if (u.onend) setTimeout(u.onend, 0); },
      cancel: () => {}, pause: () => {}, resume: () => {}, speaking: false, paused: false
    };
    // window.speechSynthesis is a read-only native accessor; a plain assignment is silently ignored.
    Object.defineProperty(window, 'speechSynthesis', { value: stub, writable: true, configurable: true });
    Object.defineProperty(window, 'SpeechSynthesisUtterance',
      { value: function (text) { this.text = text; }, writable: true, configurable: true });
  });
}

// 1. Chat page: ask a starter question, click Listen on the resulting saved-answer bubble.
{
  const env = await launch('light', 'no-preference');
  await stubSpeech(env.page);
  await login(env.page, 'demo.patient@example.com');
  await env.page.goto(B + '/chat');
  await env.page.setViewportSize({ width: 390, height: 844 });
  await env.page.waitForSelector('[data-template-id]');
  const starterText = await env.page.getAttribute('[data-template-id]', 'data-template-text');
  await env.page.click('[data-template-id]');
  await env.page.waitForSelector('.msg-bot .mfh-listen', { timeout: 25000 });
  const replyText = await env.page.locator('.msg-bot').last().locator('.msg-text').textContent();
  await env.page.screenshot({ path: SHOTS + '/listen-chat-light-390.png' });
  await env.page.locator('.msg-bot .mfh-listen').last().click();
  const calls = await env.page.evaluate(() => window.__speakCalls);
  check(calls.length === 1, 'speechSynthesis.speak called once: ' + calls.length);
  check(calls.length > 0 && replyText.includes(calls[0].text.replace(/\.$/, '').slice(0, 20)), 'spoken text matches the visible reply');
  check(calls.length > 0 && calls[0].voice && calls[0].voice.localService === true, 'only the local-only voice was used');
  check(starterText && starterText.length > 0, 'starter question text present: ' + starterText);
  const label = await env.page.locator('.msg-bot .mfh-listen').last().locator('.mfh-listen-label').textContent();
  check(label.trim() === 'Reading...' || label.trim() === 'Listen', 'label toggled (settled at: ' + label + ')');
  await env.browser.close();
}

// 2. Dashboard tip card, dark theme.
{
  const env = await launch('dark', 'no-preference');
  await stubSpeech(env.page);
  await login(env.page, 'demo.patient@example.com');
  await env.page.goto(B + '/patient/dashboard');
  await env.page.setViewportSize({ width: 390, height: 844 });
  await env.page.waitForSelector('#tip-listen');
  const tipText = await env.page.locator('[data-tip-text]').textContent();
  await env.page.locator('#tip-card').scrollIntoViewIfNeeded();
  await env.page.screenshot({ path: SHOTS + '/listen-tip-dark-390.png' });
  await env.page.click('#tip-listen');
  const calls = await env.page.evaluate(() => window.__speakCalls);
  check(calls.length === 1, 'tip card speak called once: ' + calls.length);
  check(calls.length > 0 && calls[0].text.trim() === tipText.trim(), 'spoken text matches the visible tip exactly');
  check(calls.length > 0 && calls[0].voice && calls[0].voice.localService === true, 'tip card used only the local-only voice');
  check(!!(await env.page.getAttribute('#tip-listen', 'aria-label')), 'Listen button has an aria-label');
  await env.browser.close();
}

if (failed) { console.log(failed + ' check(s) failed'); process.exit(1); }
console.log('All checks passed.');
