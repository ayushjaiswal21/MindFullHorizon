// Provider dashboard. URLs come from data-* attributes on #provider-config (static files are not rendered by Jinja).
(function () {
    'use strict';

    const cfg = (document.getElementById('provider-config') || {}).dataset || {};
    const urlWithId = (tpl, id) => (tpl || '').replace(/0$/, encodeURIComponent(id));
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const $ = id => document.getElementById(id);

    const STATUS_LABEL = { pending: 'Pending', accepted: 'Accepted', rejected: 'Rejected', completed: 'Completed', cancelled: 'Cancelled' };
    const STATUS_BADGE = { pending: 'badge-warning', accepted: 'badge-info', rejected: 'badge-danger', completed: 'badge-success', cancelled: 'badge-neutral' };

    let currentAppointmentId = null;
    let currentMessagePatientId = null;
    let currentStatus = 'all';

    const debounce = (fn, ms) => {
        if (window.MFH && typeof MFH.debounce === 'function') return MFH.debounce(fn, ms);
        let t;
        return function () { const a = arguments; clearTimeout(t); t = setTimeout(() => fn.apply(null, a), ms); };
    };

    function say(message, type) {
        if (window.MFH && typeof MFH.toast === 'function') {
            MFH.toast(message, type || 'info');
        } else {
            const live = $('appointmentsStatus');
            if (live) live.textContent = message;
        }
    }

    function csrf() {
        const m = document.querySelector('meta[name="csrf-token"]');
        return m ? m.getAttribute('content') : '';
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify(body || {})
        }).then(r => r.json().catch(() => ({})).then(data => ({ ok: r.ok, data: data })));
    }

    function openDialog(d) { if (typeof d.showModal === 'function') d.showModal(); else d.setAttribute('open', ''); }
    function closeDialog(d) { if (typeof d.close === 'function') d.close(); else d.removeAttribute('open'); }

    function colSpanRow(html) { return '<tr><td colspan="5">' + html + '</td></tr>'; }

    // ---------- appointments ----------

    function healthSummary(appointment) {
        const h = appointment.patient_health_data;
        if (!h) return '';
        const items = [];
        if (h.latest_assessment) {
            const a = h.latest_assessment;
            items.push(esc(a.type) + ': ' + esc(a.severity || 'n/a') + ' (' + esc(a.score) + ')');
        }
        if (h.vital_signs && h.vital_signs.mood_score) items.push('Mood: ' + esc(h.vital_signs.mood_score) + '/10');
        if (h.digital_wellness && h.digital_wellness.screen_time != null) items.push('Screen time: ' + esc(h.digital_wellness.screen_time) + ' h/day');
        return '<div class="help">' + (items.length ? items.join('; ') : 'No recent health data') + '</div>';
    }

    function actionsFor(a) {
        const id = esc(a.id);
        if (a.status === 'pending') {
            return '<div class="flex flex-wrap gap-2">' +
                '<button type="button" class="btn btn-primary btn-sm accept-appointment-btn" data-appointment-id="' + id + '">Accept</button>' +
                '<button type="button" class="btn btn-secondary btn-sm show-reject-modal-btn" data-appointment-id="' + id + '">Reject</button>' +
                '</div>';
        }
        if (a.status === 'accepted') {
            return '<div class="flex flex-wrap gap-2">' +
                '<button type="button" class="btn btn-primary btn-sm complete-appointment-btn" data-appointment-id="' + id + '">Mark completed</button>' +
                '<button type="button" class="btn btn-secondary btn-sm cancel-appointment-btn" data-appointment-id="' + id + '">Cancel</button>' +
                '</div>';
        }
        return '<span class="muted">No actions</span>';
    }

    function rowFor(a) {
        const status = STATUS_LABEL[a.status] ? a.status : 'pending';
        const notes = a.notes ? '<div class="help">Note: ' + esc(a.notes.length > 80 ? a.notes.slice(0, 80) + '...' : a.notes) + '</div>' : '';
        const reason = a.status === 'rejected' && a.rejection_reason ? '<div class="help">Reason: ' + esc(a.rejection_reason) + '</div>' : '';
        const unassigned = a.provider_id ? '' : ' <span class="badge badge-info">Unassigned</span>';
        const urgent = a.urgency_level === 'high' ? ' <span class="badge badge-danger">High priority</span>' : '';
        const report = a.patient_id ? '<a href="' + esc(urlWithId(cfg.reportUrl, a.patient_id)) + '" class="help">View wellness report</a>' : '';
        return '<tr>' +
            '<th scope="row"><div>' + esc(a.patient_name) + unassigned + urgent + '</div>' + healthSummary(a) + report + '</th>' +
            '<td><div>' + esc(a.date) + '</div><div class="help">' + esc(a.time) + '</div></td>' +
            '<td><div>' + esc(a.type) + (a.modality ? ' <span class="badge badge-neutral">' + (a.modality === 'video' ? 'Video' : 'In person') + '</span>' : '') + '</div>' + notes + '</td>' +
            '<td><span class="badge ' + STATUS_BADGE[status] + '">' + STATUS_LABEL[status] + '</span>' + reason + '</td>' +
            '<td>' + actionsFor(a) + '</td>' +
            '</tr>';
    }

    function updateCounts(list) {
        const n = s => list.filter(a => a.status === s).length;
        $('allCount').textContent = list.length;
        $('pendingBadge').textContent = n('pending');
        $('acceptedCount').textContent = n('accepted');
        $('completedCount').textContent = n('completed');
        $('rejectedCount').textContent = n('rejected');
        $('cancelledCount').textContent = n('cancelled');
        const pending = n('pending');
        $('pendingCount').textContent = pending;
        $('pendingNotification').hidden = pending === 0;
    }

    window.displayAppointments = function (appointments) {
        const tbody = $('appointmentsBody');
        if (!tbody) return;
        const list = appointments || [];
        // Counts reflect the current filter's result set; "All" is the only unfiltered view.
        if (currentStatus === 'all') updateCounts(list);
        if (!list.length) {
            tbody.innerHTML = colSpanRow('<div class="empty-state"><h3>No appointments' + (currentStatus === 'all' ? '' : ' with this status') + '</h3><p>Appointment requests from your students appear here.</p></div>');
            return;
        }
        tbody.innerHTML = list.map(rowFor).join('');
    };

    window.loadAppointments = function (status) {
        currentStatus = status || currentStatus || 'all';
        const tbody = $('appointmentsBody');
        const live = $('appointmentsStatus');
        if (live) live.textContent = 'Loading appointments';
        fetch(cfg.appointmentsUrl + '?status=' + encodeURIComponent(currentStatus), {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        })
            .then(r => r.json().catch(() => ({})).then(data => ({ ok: r.ok, data: data })))
            .then(res => {
                if (live) live.textContent = '';
                if (res.ok && res.data && res.data.success) {
                    window.displayAppointments(res.data.appointments);
                } else {
                    tbody.innerHTML = colSpanRow('<span class="text-danger">Appointments could not be loaded. Use Refresh to try again.</span>');
                }
            })
            .catch(() => {
                if (live) live.textContent = '';
                tbody.innerHTML = colSpanRow('<span class="text-danger">Appointments could not be loaded. Check your connection and use Refresh to try again.</span>');
            });
    };

    window.filterAppointments = function (status) {
        document.querySelectorAll('.filter-appointments-btn').forEach(btn => {
            const on = btn.dataset.status === status;
            btn.classList.toggle('active', on);
            btn.setAttribute('aria-pressed', String(on));
        });
        window.loadAppointments(status);
    };

    window.refreshAppointments = function () { window.loadAppointments(); };

    // After any change reload the full list so the counts stay right.
    function reloadAll() { window.filterAppointments('all'); }

    function act(url, body, okMessage, failMessage, button) {
        if (button) button.disabled = true;
        postJson(url, body).then(res => {
            if (res.ok && res.data && res.data.success) {
                say(okMessage, 'success');
                reloadAll();
            } else {
                say((res.data && res.data.message) || failMessage, 'error');
                if (button) button.disabled = false;
            }
        }).catch(() => {
            say(failMessage, 'error');
            if (button) button.disabled = false;
        });
    }

    window.acceptAppointment = function (id, button) {
        act(urlWithId(cfg.acceptUrl, id), {}, 'Appointment accepted. The student has been notified.', 'Could not accept the appointment. Try again.', button);
    };

    window.showRejectModal = function (id) {
        currentAppointmentId = id;
        $('rejectionReason').value = '';
        $('rejectionReason').removeAttribute('aria-invalid');
        $('rejectionError').hidden = true;
        openDialog($('rejectionModal'));
        $('rejectionReason').focus();
    };

    function completeAppointment(id, button) {
        act(urlWithId(cfg.completeUrl, id), {}, 'Appointment marked as completed.', 'Could not mark the appointment as completed. Try again.', button);
    }

    function cancelAppointment(id, button) {
        const run = () => act(urlWithId(cfg.cancelUrl, id), {}, 'Appointment cancelled. The student has been notified.', 'Could not cancel the appointment. Try again.', button);
        if (window.MFH && typeof MFH.confirm === 'function') {
            MFH.confirm({ title: 'Cancel this appointment?', message: 'The student will be told the appointment is cancelled.', confirmText: 'Cancel appointment', danger: true })
                .then(ok => { if (ok) run(); });
        } else {
            run();
        }
    }

    // ---------- messages ----------

    function openMessage(patientId, name) {
        currentMessagePatientId = patientId;
        $('messageTo').textContent = 'To: ' + (name || 'student');
        $('messageText').value = '';
        $('messageText').removeAttribute('aria-invalid');
        $('messageError').hidden = true;
        openDialog($('messageDialog'));
        $('messageText').focus();
    }

    function sendMessage() {
        const text = $('messageText').value.trim();
        if (!text) {
            $('messageError').hidden = false;
            $('messageText').setAttribute('aria-invalid', 'true');
            $('messageText').focus();
            return;
        }
        const btn = $('sendMessage');
        btn.disabled = true;
        postJson(cfg.messageUrl, { recipient_id: currentMessagePatientId, message: text }).then(res => {
            btn.disabled = false;
            if (res.ok && res.data && res.data.success) {
                closeDialog($('messageDialog'));
                say('Message sent.', 'success');
            } else {
                say('The message was not sent. Try again.', 'error');
            }
        }).catch(() => {
            btn.disabled = false;
            say('The message was not sent. Check your connection and try again.', 'error');
        });
    }

    // ---------- caseload filter (client side, on top of the server-side form) ----------

    function filterCaseload() {
        const rows = document.querySelectorAll('#caseloadTable tbody tr');
        if (!rows.length) return;
        const q = ($('caseloadSearch').value || '').trim().toLowerCase();
        const risk = $('caseloadRisk').value;
        let shown = 0;
        rows.forEach(row => {
            const hay = ((row.dataset.riskName || '') + ' ' + (row.dataset.email || '')).toLowerCase();
            const match = (!q || hay.indexOf(q) !== -1) && (!risk || row.dataset.risk === risk);
            row.hidden = !match;
            if (match) shown++;
        });
        const none = $('caseloadNoMatch');
        if (none) none.hidden = shown !== 0;
    }

    // ---------- wiring ----------

    document.addEventListener('DOMContentLoaded', function () {
        window.loadAppointments('all');

        // base.html opens the shared socket (window.socket) before this script runs.
        if (window.socket) {
            window.socket.on('new_appointment', function (data) {
                say('New appointment request from ' + ((data && data.patient_name) || 'a student') + '.', 'info');
                window.loadAppointments();
            });
        }

        $('refresh-appointments-btn').addEventListener('click', window.refreshAppointments);
        document.querySelectorAll('.filter-appointments-btn').forEach(btn => {
            btn.addEventListener('click', () => window.filterAppointments(btn.dataset.status));
        });

        $('appointmentsBody').addEventListener('click', function (event) {
            const btn = event.target.closest('button');
            if (!btn) return;
            const id = btn.dataset.appointmentId;
            if (btn.classList.contains('accept-appointment-btn')) window.acceptAppointment(id, btn);
            else if (btn.classList.contains('show-reject-modal-btn')) window.showRejectModal(id);
            else if (btn.classList.contains('complete-appointment-btn')) completeAppointment(id, btn);
            else if (btn.classList.contains('cancel-appointment-btn')) cancelAppointment(id, btn);
        });

        $('cancelReject').addEventListener('click', () => { closeDialog($('rejectionModal')); currentAppointmentId = null; });
        $('confirmReject').addEventListener('click', function () {
            const field = $('rejectionReason');
            const reason = field.value.trim();
            if (!reason) {
                $('rejectionError').hidden = false;
                field.setAttribute('aria-invalid', 'true');
                field.focus();
                return;
            }
            closeDialog($('rejectionModal'));
            act(urlWithId(cfg.rejectUrl, currentAppointmentId), { reason: reason }, 'Appointment rejected. The student has been notified with your reason.', 'Could not reject the appointment. Try again.', null);
            currentAppointmentId = null;
        });

        document.body.addEventListener('click', function (event) {
            const btn = event.target.closest('.open-message-btn');
            if (btn) openMessage(btn.dataset.patientId, btn.dataset.patientName);
        });
        $('cancelMessage').addEventListener('click', () => closeDialog($('messageDialog')));
        $('sendMessage').addEventListener('click', sendMessage);

        const filterDebounced = debounce(filterCaseload, 200);
        $('caseloadSearch').addEventListener('input', filterDebounced);
        $('caseloadRisk').addEventListener('change', filterCaseload);
        filterCaseload();
    });
})();
