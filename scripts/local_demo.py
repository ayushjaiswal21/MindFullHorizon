"""Local demo: a throwaway SQLite database, demo accounts with KNOWN passwords, sample data, then the dev server.

    python scripts/local_demo.py              # seed (first run) and start http://127.0.0.1:5000
    python scripts/local_demo.py --reset      # delete the demo database first, then seed and start
    python scripts/local_demo.py --no-run     # seed only

For local testing only. It refuses to run when FLASK_ENV=production, and the shared password below is public:
never use it for a real deployment (see docs/DEPLOY.md for the production admin bootstrap).
"""
import argparse
import os
import sys
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEMO_PASSWORD = 'Demo@Pass2026'
DEMO_DB = os.path.join(ROOT, 'instance', 'demo.db')
EXTRA_PATIENTS = [  # key, email, name, institution
    ('patient2', 'demo.patient2@example.com', 'Demo Patient Two', 'Demo University'),
    ('patient3', 'demo.patient3@other.example', 'Other College Patient', 'Other College'),
]


def _env():
    if os.getenv('FLASK_ENV') == 'production':
        sys.exit('Refusing to run the local demo when FLASK_ENV=production.')
    os.environ.setdefault('FLASK_ENV', 'development')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///' + DEMO_DB.replace('\\', '/'))
    os.environ.setdefault('SECRET_KEY', 'local-demo-secret-not-for-production')
    os.environ.setdefault('PROVIDER_INVITE_CODE', 'demo-counsellor-code')
    os.environ.setdefault('DOCTOR_INVITE_CODE', 'demo-doctor-code')
    os.environ.setdefault('ENABLE_PRESCRIPTIONS', '1')
    os.environ.setdefault('JOBS_INPROCESS', '1')
    os.environ.setdefault('SITE_URL', 'http://127.0.0.1:5000')


def _ensure_user(db, User, email, name, institution):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name, role='patient', institution=institution)
        user.set_password(DEMO_PASSWORD)  # password_hash is NOT NULL
        db.session.add(user)
    return user


def _sample_data(db, users):
    """Idempotent sample rows so the dashboards are not empty. All fictional."""
    from models import (Appointment, Assessment, DigitalDetoxLog, Goal, JournalEntry, MoodLog, ProviderPatient)
    from utils.timeutil import ist_today, utcnow
    now, today = utcnow(), ist_today()
    p1, p2, counsellor = users['patient'], users['patient2'], users['counsellor']
    if not MoodLog.query.filter_by(user_id=p1.id).first():
        for i, score in enumerate([5, 6, 4, 5, 7, 6, 6, 5, 7, 8, 6, 7, 7, 8]):
            db.session.add(MoodLog(user_id=p1.id, mood_score=score, created_at=now - timedelta(days=13 - i)))
        db.session.add(Assessment(user_id=p1.id, assessment_type='PHQ-9', score=12,
                                  responses=[2, 2, 2, 2, 2, 1, 1, 0, 0], created_at=now - timedelta(days=9)))
        db.session.add(Assessment(user_id=p1.id, assessment_type='GAD-7', score=8,
                                  responses=[1, 1, 2, 1, 1, 1, 1], created_at=now - timedelta(days=9)))
        db.session.add(JournalEntry(user_id=p1.id, title='Exam week', content='Slept badly, but a walk helped.'))
        db.session.add(Goal(user_id=p1.id, title='Walk 20 minutes daily', category='physical',
                            target_value=20, current_value=8, unit='minutes', start_date=today))
        db.session.add(DigitalDetoxLog(user_id=p1.id, date=today - timedelta(days=1), screen_time_hours=5.5,
                                       academic_score=7, social_interactions='medium'))
    if not Assessment.query.filter_by(user_id=p2.id).first():
        for i, score in enumerate([3, 2, 3, 2, 2]):
            db.session.add(MoodLog(user_id=p2.id, mood_score=score, created_at=now - timedelta(days=4 - i)))
        db.session.add(Assessment(user_id=p2.id, assessment_type='PHQ-9', score=22,
                                  responses=[3, 3, 3, 3, 2, 2, 2, 2, 2], created_at=now - timedelta(days=1)))
    if not ProviderPatient.query.filter_by(provider_id=counsellor.id, patient_id=p2.id).first():
        db.session.add(ProviderPatient(provider_id=counsellor.id, patient_id=p2.id, source='manual'))
    if not Appointment.query.filter_by(user_id=p2.id).first():
        db.session.add(Appointment(user_id=p2.id, provider_id=counsellor.id, date=today + timedelta(days=1),
                                   time='11:00', appointment_type='Counselling', status='pending',
                                   client_request_id='demo-p2-appointment'))
    db.session.flush()
    return p2


def seed():
    from app import app
    from extensions import db
    from models import CrisisEvent, User
    from scripts.seed_demo import seed as seed_base
    with app.app_context():
        db.create_all()
    seed_base(force=True)  # random passwords are replaced below; unchanged rows stay as they are
    with app.app_context():
        users = {'patient': User.query.filter_by(email='demo.patient@example.com').first(),
                 'counsellor': User.query.filter_by(email='demo.provider@example.com').first()}
        for key, email, name, inst in EXTRA_PATIENTS:
            users[key] = _ensure_user(db, User, email, name, inst)
        db.session.flush()
        p2 = _sample_data(db, users)
        db.session.commit()
        if not CrisisEvent.query.filter_by(user_id=p2.id).first():  # makes the counsellor's crisis panel show a case
            from utils.crisis import record_crisis
            record_crisis(p2.id, 'phq9', 9, 'phq9 item 9 above zero')
            db.session.commit()
        from models import ConsentRecord
        version = os.environ.get('CONSENT_VERSION', '2026-11')
        for u in User.query.filter(User.email.like('demo.%')).all():
            u.set_password(DEMO_PASSWORD)
            for kind in ('privacy', 'age18'):  # demo users have already accepted, so login goes straight to the dashboard
                if not ConsentRecord.query.filter_by(user_id=u.id, kind=kind, version=version).first():
                    db.session.add(ConsentRecord(user_id=u.id, kind=kind, version=version))
        db.session.commit()
        return [(u.email, u.role, u.provider_type or '', u.institution) for u in User.query.order_by(User.id).all()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reset', action='store_true', help='delete the demo database first')
    ap.add_argument('--no-run', action='store_true', help='seed only, do not start the server')
    ap.add_argument('--port', type=int, default=5000)
    args = ap.parse_args()
    _env()
    url = os.environ['DATABASE_URL']
    db_file = url.split('sqlite:///', 1)[1] if url.startswith('sqlite:///') else None  # honour a DATABASE_URL override
    if db_file:
        if args.reset and os.path.exists(db_file):
            os.remove(db_file)
        os.makedirs(os.path.dirname(db_file) or '.', exist_ok=True)
    rows = seed()
    print(f'\nDemo accounts (all use the password  {DEMO_PASSWORD} ):')
    for email, role, ptype, inst in rows:
        print(f'  {email:34} {role:9} {ptype:11} {inst}')
    print(f'Counsellor signup code: {os.environ["PROVIDER_INVITE_CODE"]}   Doctor signup code: {os.environ["DOCTOR_INVITE_CODE"]}')
    if args.no_run:
        return
    from app import app, socketio
    print(f'\nOpen http://127.0.0.1:{args.port}  (Ctrl+C to stop)')
    socketio.run(app, host='127.0.0.1', port=args.port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
