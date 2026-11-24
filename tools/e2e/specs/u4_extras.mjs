import { launch, login, B } from '../lib.mjs';
const OUT = process.env.SHOTS;
for (const scheme of ['light', 'dark']) {
  const { browser, page } = await launch(scheme);
  await page.goto(B + '/'); await page.evaluate(() => { try { localStorage.setItem('mfh_consent', JSON.stringify({a:false})); } catch (e) {} });
  // in-page theme toggle: flip once, record resulting attribute
  await page.click('[data-theme-toggle]');
  console.log(scheme, 'after toggle data-theme =', await page.getAttribute('html', 'data-theme'));
  await page.click('[data-theme-toggle]'); // back
  await page.evaluate(() => { MFH.toast('Saved your mood entry.', 'success'); MFH.toast('Something went wrong. Try again.', 'error'); MFH.toast('Your session will end soon.', 'info'); });
  await page.screenshot({ path: `${OUT}/${scheme}-toasts.png` });
  // crisis banner + badges + table + alerts sample injected in page using real classes
  await page.evaluate(() => {
    const m = document.querySelector('main'); const d = document.createElement('div'); d.className = 'container'; d.id = 'u4';
    d.innerHTML = '<div class="crisis-banner"><p>If you are in danger call <a href="tel:14416">Tele-MANAS 14416</a></p></div>' +
    '<div class="alert alert-danger"><p>Danger alert text</p></div><div class="alert alert-warning"><p>Warning alert text</p></div><div class="alert alert-success"><p>Success alert text</p></div><div class="alert alert-info"><p>Info alert text</p></div>' +
    '<p><span class="badge badge-neutral">Neutral</span> <span class="badge badge-success">Success</span> <span class="badge badge-warning">Warning</span> <span class="badge badge-danger">Danger</span> <span class="badge badge-info">Info</span></p>' +
    '<div class="table-wrap"><table class="table"><thead><tr><th>Name</th><th>Status</th></tr></thead><tbody><tr><td>Row one</td><td><span class="badge badge-success">Active</span></td></tr><tr><td>Row two</td><td class="muted">Muted text</td></tr></tbody></table></div>' +
    '<p><button class="btn btn-primary">Primary</button> <button class="btn btn-secondary">Secondary</button> <button class="btn btn-danger">Danger</button> <button class="btn btn-ghost">Ghost</button> <input class="input" style="width:12rem" placeholder="Placeholder" aria-invalid="true"> <a href="#">A link</a></p>';
    m.prepend(d);
  });
  await page.keyboard.press('Tab');
  await page.screenshot({ path: `${OUT}/${scheme}-components.png`, clip: { x: 0, y: 0, width: 1280, height: 900 } });
  await browser.close();
}
