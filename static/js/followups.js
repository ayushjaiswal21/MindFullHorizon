// Follow-up tracker, caseload flag filter and appointment reminder notes (provider dashboard and wellness report).
// URLs come from data-* attributes on [data-fu-root]; no server values are written into this file.
(function () {
    'use strict';

    const $ = id => document.getElementById(id);
    const root = document.querySelector('[data-fu-root]');
    const cfg = root ? root.dataset : {};
    const withId = (tpl, id) => (tpl || '').replace(/0$/, encodeURIComponent(id));
    const say = (m, t) => { if (window.MFH && MFH.toast) MFH.toast(m, t || 'info'); };
    const csrf = () => { const m = document.querySelector('meta[name="csrf-token"]'); return m ? m.getAttribute('content') : ''; };

    function post(url, body) {
        return fetch(url, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify(body)
        }).then(r => r.json().catch(() => ({})).then(d => ({ ok: r.ok, data: d })));
    }

    function open(d) { if (d.showModal) d.showModal(); else d.setAttribute('open', ''); }
    function close(d) { if (d.close) d.close(); else d.removeAttribute('open'); }

    function send(url, body, okMessage, buttons) {
        buttons.forEach(b => { b.disabled = true; });
        post(url, body).then(res => {
            if (res.ok && res.data && res.data.success) {
                say(okMessage, 'success');
                setTimeout(() => window.location.reload(), 700);
            } else {
                say((res.data && res.data.message) || 'The change was not saved. Try again.', 'error');
                buttons.forEach(b => { b.disabled = false; });
            }
        }).catch(() => {
            say('The change was not saved. Check your connection and try again.', 'error');
            buttons.forEach(b => { b.disabled = false; });
        });
    }

    // ---------- mark a step done, missed or skipped ----------

    let stepId = null;
    const dlg = $('fuDoneDialog');
    if (dlg && root) {
        const buttons = () => Array.prototype.slice.call(dlg.querySelectorAll('button'));
        const submit = (action, msg) => send(withId(cfg.stepUrl, stepId),
            { action: action, outcome: action === 'done' ? $('fuOutcome').value : null, note: $('fuNote').value }, msg, buttons());
        document.addEventListener('click', e => {
            const btn = e.target.closest('[data-fu-done]');
            if (!btn) return;
            stepId = btn.dataset.stepId;
            $('fuDoneFor').textContent = 'Follow-up ' + btn.dataset.seq + ' for ' + btn.dataset.name + '.';
            $('fuOutcome').value = btn.dataset.suggest || 'contacted_by_phone';
            $('fuNote').value = '';
            buttons().forEach(b => { b.disabled = false; });
            open(dlg);
            $('fuOutcome').focus();
        });
        $('fuDoneCancel').addEventListener('click', () => close(dlg));
        $('fuDoneSave').addEventListener('click', () => submit('done', 'Follow-up recorded.'));
        dlg.querySelectorAll('[data-fu-alt]').forEach(b => b.addEventListener('click', () =>
            submit(b.dataset.fuAlt, b.dataset.fuAlt === 'missed' ? 'Follow-up marked missed.' : 'Follow-up skipped.')));
    }

    // ---------- close a plan early (report page) ----------

    let planId = null;
    const cd = $('fuCloseDialog');
    if (cd && root) {
        document.addEventListener('click', e => {
            const btn = e.target.closest('[data-fu-close]');
            if (!btn) return;
            planId = btn.dataset.planId;
            open(cd);
            $('fuCloseReason').focus();
        });
        $('fuCloseCancel').addEventListener('click', () => close(cd));
        $('fuCloseSave').addEventListener('click', () =>
            send(withId(cfg.closeUrl, planId), { reason: $('fuCloseReason').value }, 'Plan closed.', [$('fuCloseSave'), $('fuCloseCancel')]));
    }

    // ---------- caseload: show only students whose screening score rose ----------

    const flagBox = $('caseloadFlagged');
    function applyFlagFilter() {
        const on = flagBox.checked;
        let shown = 0;
        document.querySelectorAll('#caseloadTable tbody tr').forEach(row => {
            const hide = on && row.dataset.flag !== '1';
            row.classList.toggle('fu-flag-hidden', hide);
            if (!hide && !row.hidden) shown++;
        });
        const none = $('caseloadNoMatch');
        if (none && on && shown === 0) { none.hidden = false; }
    }
    if (flagBox) {
        flagBox.checked = new URLSearchParams(window.location.search).get('flag') === '1';
        flagBox.addEventListener('change', applyFlagFilter);
        applyFlagFilter();
    }

    // ---------- appointment rows: say honestly whether a reminder job exists ----------

    const original = window.displayAppointments;
    if (typeof original === 'function' && cfg.remindersUrl) {
        window.displayAppointments = function (list) {
            original(list);
            fetch(cfg.remindersUrl, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
                .then(r => r.json())
                .then(data => {
                    const map = (data && data.reminders) || {};
                    document.querySelectorAll('#appointmentsBody tr').forEach(row => {
                        const b = row.querySelector('[data-appointment-id]');
                        const info = b && map[b.dataset.appointmentId];
                        const cell = row.children[3];
                        if (!info || !cell || cell.querySelector('.fu-reminder')) return;
                        const note = document.createElement('span');
                        note.className = 'help fu-reminder';
                        note.textContent = info.state === 'sent' ? 'Reminder sent' : 'Reminder scheduled';
                        cell.appendChild(note);
                    });
                })
                .catch(() => { /* the note is optional; the list itself is already shown */ });
        };
    }
})();
