"""Query-count guard for the pages that carry the follow-up panel, caseload flags and report timeline (see test_perf.py)."""
from datetime import timedelta

from extensions import db
from models import Assessment, CrisisEvent, FollowUpPlan, FollowUpStep, ProviderPatient
from test_perf import _count_queries, _seed_caseload
from utils.timeutil import ist_today, utcnow


def _flags_and_plans(app, pid):
    """A flagged second PHQ-9 and an open plan with three steps for every assigned patient that has none yet."""
    with app.app_context():
        have = {p.patient_id for p in FollowUpPlan.query.all()}
        for (uid,) in db.session.query(ProviderPatient.patient_id).filter_by(provider_id=pid).all():
            if uid in have:
                continue
            db.session.add(Assessment(user_id=uid, assessment_type='PHQ-9', score=25, created_at=utcnow() + timedelta(minutes=1)))
            ev = CrisisEvent(user_id=uid, source='phq9', severity=9, reason='x', acknowledged_at=utcnow(), acknowledged_by=pid)
            db.session.add(ev)
            db.session.flush()
            plan = FollowUpPlan(crisis_event_id=ev.id, patient_id=uid, owner_provider_id=pid)
            plan.steps = [FollowUpStep(seq=i + 1, due_date=ist_today() + timedelta(days=d)) for i, d in enumerate((-1, 0, 5))]
            db.session.add(plan)
        db.session.commit()


def test_dashboard_with_flags_and_followups_is_flat_for_30_patients(app, provider_client):
    c, pid = provider_client
    _seed_caseload(app, pid, 3)
    _flags_and_plans(app, pid)
    few = _count_queries(app, lambda: c.get('/provider/dashboard'))
    _seed_caseload(app, pid, 30)
    _flags_and_plans(app, pid)
    many = _count_queries(app, lambda: c.get('/provider/dashboard'))
    page = c.get('/provider/dashboard').get_data(as_text=True)
    assert 'Score up' in page and 'Follow-up 1 of 3' in page
    assert many <= 30, many
    assert many <= few + 2, (few, many)


def test_report_with_timeline_is_flat_in_plan_and_history_length(app, provider_client):
    c, pid = provider_client
    _seed_caseload(app, pid, 3)
    _flags_and_plans(app, pid)
    with app.app_context():
        uid = db.session.query(ProviderPatient.patient_id).filter_by(provider_id=pid).first()[0]
    short = _count_queries(app, lambda: c.get(f'/provider/wellness-report/{uid}'))
    with app.app_context():
        for i in range(40):
            db.session.add(Assessment(user_id=uid, assessment_type='GAD-7', score=i % 20, created_at=utcnow() - timedelta(days=i + 2)))
        db.session.commit()
    long = _count_queries(app, lambda: c.get(f'/provider/wellness-report/{uid}'))
    assert long <= short + 1, (short, long)
