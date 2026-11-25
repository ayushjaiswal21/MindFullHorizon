"""Dev-only: create demo users and demo clinical data with random passwords (printed once).

Usage:  python scripts/seed_demo.py            (refuses to run when FLASK_ENV=production)
        python scripts/seed_demo.py --force    (only for a throwaway database that is NOT real: you take the risk)

Creates: a demo patient, a demo counsellor, a demo doctor (verified profile marked DEMO), two demo admins (one is
the pharmacy desk), about eight FICTIONAL medicines marked DEMO with batches, a started video consult, the patient's
e-prescription consent and one sample prescription. Safe to run twice: existing rows are left unchanged.
"""
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# key, email, display name, role, provider_type, pharmacy desk
DEMO_USERS = [
    ('patient', 'demo.patient@example.com', 'Demo Patient', 'patient', None, False),
    ('counsellor', 'demo.provider@example.com', 'Demo Provider', 'provider', 'counsellor', False),
    ('doctor', 'demo.doctor@example.com', 'Demo Doctor', 'provider', 'doctor', False),
    ('admin', 'demo.admin@example.com', 'Demo Admin', 'admin', None, True),
    ('admin2', 'demo.admin2@example.com', 'Demo Admin Two', 'admin', None, False),
]


def seed(force=False):
    if os.getenv('FLASK_ENV') == 'production' and not force:
        sys.exit('Refusing to seed demo users when FLASK_ENV=production (use --force only on a throwaway database).')
    from app import app
    from core.extensions import db
    from models import User
    from scripts.seed_clinical import DEMO_INSTITUTION, seed_clinical
    from utils.timeutil import ist_today, utcnow

    created, users, notes = [], {}, []
    with app.app_context():
        for key, email, name, role, ptype, desk in DEMO_USERS:
            user = User.query.filter_by(email=email).first()
            if user:
                print(f'{email} already exists; left unchanged (password not shown).')
            else:
                password = secrets.token_urlsafe(12)
                user = User(email=email, name=name, role=role, institution=DEMO_INSTITUTION,
                            provider_type=ptype, is_pharmacy_desk=desk)
                user.set_password(password)
                db.session.add(user)
                created.append((email, password))
            users[key] = user
        db.session.flush()
        notes = seed_clinical(db, users, utcnow, ist_today)
        db.session.commit()
    for email, password in created:
        print(f'{email}  password: {password}')
    for line in notes:
        print(line)
    if created:
        print('Passwords are shown only once. Demo medicines are marked DEMO and are blocked in production.')


if __name__ == '__main__':
    seed(force='--force' in sys.argv[1:])
