"""Redesigned provider pages: dashboard, analytics, telehealth, wellness report."""
import re
from datetime import date, datetime, timedelta

import pytest

from extensions import db
from models import (Appointment, Assessment, ClinicalNote, CrisisEvent, DigitalDetoxLog, ProviderPatient,
                    RPMData)

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌]")
FORBIDDEN_TEXT = ["—", "–", "None%", "None h", "NaN", "undefined", "Powered by AI", "AI-Powered"]


def add(app, obj):
    with app.app_context():
        db.session.add(obj)
        db.session.commit()
        return obj.id


def link(app, provider_id, patient_id):
    """Make the patient reachable under both the old (appointment) and new (assignment) scope."""
    add(app, Appointment(user_id=patient_id, provider_id=provider_id, date=date.today(), time="10:00",
                         appointment_type="video"))
    with app.app_context():
        if not ProviderPatient.query.filter_by(provider_id=provider_id, patient_id=patient_id).first():
            db.session.add(ProviderPatient(provider_id=provider_id, patient_id=patient_id, source="manual"))
            db.session.commit()


def fill(app, patient_id):
    add(app, Assessment(user_id=patient_id, assessment_type="PHQ-9", score=12))
    add(app, Assessment(user_id=patient_id, assessment_type="GAD-7", score=6))
    add(app, DigitalDetoxLog(user_id=patient_id, date=date.today(), screen_time_hours=4, academic_score=70,
                             social_interactions="moderate", ai_score="Good"))
    add(app, RPMData(user_id=patient_id, date=date.today(), mood_score=6))
    add(app, ClinicalNote(provider_id=1, patient_id=patient_id, session_date=datetime.now(), provider_notes="Seen"))


def check_clean(html):
    """Checks this page's own markup (from its stylesheet link to the end of <main>), not the shared shell."""
    start = html.index("css/provider.css")
    end = html.find("</main>", start)
    html = html[start:end if end != -1 else len(html)]
    assert not EMOJI.search(html), EMOJI.search(html)
    for bad in FORBIDDEN_TEXT:
        assert bad not in html, bad
    assert "rounded-full" not in html and "gradient" not in html


def pages(patient_id):
    return ["/provider/dashboard", "/provider/analytics", f"/provider/telehealth/{patient_id}",
            f"/provider/wellness-report/{patient_id}"]


def test_pages_render_without_data(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", name="Empty Student")
    link(app, pid, p)
    for url in pages(p):
        r = c.get(url)
        assert r.status_code == 200, url
        check_clean(r.get_data(as_text=True))


def test_pages_render_with_data(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", name="Full Student")
    link(app, pid, p)
    fill(app, p)
    for url in pages(p):
        r = c.get(url)
        assert r.status_code == 200, url
        check_clean(r.get_data(as_text=True))


def test_empty_states(app, make_user, provider_client):
    c, pid = provider_client
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert "empty-state" in html
    assert "No patients assigned yet" in html
    assert "Students appear here after they book a session with you." in html
    analytics = c.get("/provider/analytics").get_data(as_text=True)
    assert "empty-state" in analytics and "Too few students to show" in analytics
    p = make_user("patient")
    link(app, pid, p)
    report = c.get(f"/provider/wellness-report/{p}").get_data(as_text=True)
    assert report.count("empty-state") >= 4
    assert "not a diagnosis" in report


def test_small_groups_show_na_and_note(app, make_user, provider_client):
    c, pid = provider_client
    for _ in range(3):
        fill(app, make_user("patient"))
    for url in ("/provider/dashboard", "/provider/analytics"):
        html = c.get(url).get_data(as_text=True)
        assert "Too few students to show" in html
        assert "n/a" in html


def test_large_group_shows_real_numbers(app, make_user, provider_client):
    c, _ = provider_client
    for _ in range(5):
        fill(app, make_user("patient"))
    html = c.get("/provider/analytics").get_data(as_text=True)
    assert "Too few students to show" not in html.split('id="trends-heading"')[0]
    assert re.search(r'stat-label">Students</div>\s*<div class="stat-value">5<', html)


def test_crisis_panel_has_no_patient_text(app, make_user, provider_client):
    c, _ = provider_client
    p = make_user("patient", name="Crisis Person")
    ev = add(app, CrisisEvent(user_id=p, source="chat", severity=3, reason="SECRET_REASON_CODE"))
    html = c.get("/provider/dashboard").get_data(as_text=True)
    assert 'role="alert"' in html and "crisis-heading" in html
    assert f"/provider/crisis/{ev}/acknowledge" in html
    assert "source: chat" in html and "severity 3" in html
    assert "SECRET_REASON_CODE" not in html
    check_clean(html)


def test_no_crisis_panel_when_none(provider_client):
    c, _ = provider_client
    assert "crisis-heading" not in c.get("/provider/dashboard").get_data(as_text=True)


def test_prescriptions_hidden_when_flag_off(app, make_user, provider_client, monkeypatch):
    c, pid = provider_client
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "0")  # default is ON since the clinical build
    p = make_user("patient")
    link(app, pid, p)
    html = c.get(f"/provider/wellness-report/{p}").get_data(as_text=True)
    assert "send_prescription" not in html and "Send prescription" not in html
    assert "prescri" not in c.get("/provider/dashboard").get_data(as_text=True).lower()


def test_medications_panel_replaces_prescription_form(app, make_user, provider_client, monkeypatch):
    c, pid = provider_client
    monkeypatch.setenv("ENABLE_PRESCRIPTIONS", "1")
    p = make_user("patient")
    link(app, pid, p)
    html = c.get(f"/provider/wellness-report/{p}").get_data(as_text=True)
    assert "send_prescription" not in html and 'id="meds-panel"' in html


def test_dashboard_js_hooks_preserved(provider_client):
    c, _ = provider_client
    html = c.get("/provider/dashboard").get_data(as_text=True)
    for needle in ('id="appointmentsBody"', 'id="refresh-appointments-btn"', 'id="pendingNotification"',
                   'id="rejectionModal"', 'id="rejectionReason"', 'id="confirmReject"', 'id="cancelReject"',
                   'id="allCount"', 'id="pendingBadge"', 'id="acceptedCount"', 'id="rejectedCount"',
                   'data-status="pending"', 'data-complete-url="/provider/appointments/complete/0"',
                   'data-cancel-url="/provider/appointments/cancel/0"'):
        assert needle in html, needle
    assert " onclick=" not in html and " onchange=" not in html


def test_telehealth_markup(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient")
    link(app, pid, p)
    html = c.get(f"/provider/telehealth/{p}").get_data(as_text=True)
    assert f'data-room="telehealth_room_{p}"' in html and "data-home-url=" in html
    for needle in ('id="telehealth-status"', 'id="mute-audio"', 'id="mute-video"', 'id="end-call"',
                   'aria-pressed="false"', "data-confirm=", "Video may fail on some networks"):
        assert needle in html, needle


def test_wellness_report_print_controls(app, make_user, provider_client):
    c, pid = provider_client
    p = make_user("patient", name="Print Person")
    link(app, pid, p)
    fill(app, p)
    html = c.get(f"/provider/wellness-report/{p}").get_data(as_text=True)
    assert 'id="report-data"' in html and "Print Person" in html
    assert "no-print" in html and 'id="print-report-btn"' in html
    assert "<details" in html and "PHQ-9" in html
    assert " onclick=" not in html


def test_static_js_uses_no_dialogs_or_handlers():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("provider_dashboard.js", "provider-charts.js", "inline_extracted/analytics_inline_1.js",
                "inline_extracted/telehealth_inline_1.js", "inline_extracted/wellness_report_inline_1.js"):
        text = open(os.path.join(root, "static", "js", rel), encoding="utf-8").read()
        assert not re.search(r"(?<![.\w])(alert|confirm|prompt)\(", text.replace("MFH.confirm(", "")), rel
        assert "onclick" not in text and "{{" not in text, rel
        assert not EMOJI.search(text), rel
