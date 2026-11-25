"""Print every GET page of the Flask url map, one path per line (used by tools/e2e/specs/csp_sweep.mjs).

Rules without parameters are printed as they are. Parameterised rules are filled from the demo database (first blog
post, a seeded prescription, a provider/patient id); a rule that cannot be filled is skipped. Run from the project
root with the demo server's DATABASE_URL:
    python tools/e2e/csp_routes.py            # print the paths (seeds one prescription first if none exists)
    python tools/e2e/csp_routes.py --all      # list the parameterised rules too, marked with '#'
"""
import itertools
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('FLASK_ENV', 'development')
SKIP = ('/logout', '/static', '/csp-report', '/login/google', '/download', '/export', '/api/', '/socket.io', '/audio', '.csv',
        '/favicon.ico', '/sitemap.xml', '/robots.txt', '/health', '/ready')  # not pages: the browser's XML/image viewer adds inline styles


def _seed_prescription(app):
    """One issued prescription from demo.doctor to demo.patient, with consent, so the rx pages can be visited."""
    from models import Prescription, User
    from tests.rx_helpers import consent_row, make_medicine, make_rx
    with app.app_context():
        doctor = User.query.filter_by(email='demo.doctor@example.com').first()
        patient = User.query.filter_by(email='demo.patient@example.com').first()
        if not doctor or not patient or Prescription.query.filter_by(patient_id=patient.id).first():
            return
        doctor_id, patient_id = doctor.id, patient.id
    consent_row(app, patient_id)
    make_rx(app, doctor_id, patient_id, make_medicine(app))


def _seed_blog(app):
    from core.extensions import db
    from models import BlogPost, User
    with app.app_context():
        author = User.query.filter_by(email='demo.provider@example.com').first()
        if author and not BlogPost.query.first():
            db.session.add(BlogPost(title='Sleep and exams', content='Short, regular sleep routines help.', author_id=author.id))
            db.session.commit()


def _values(app):
    from models import BlogPost, Medicine, PrescriberProfile, Prescription, User
    with app.app_context():
        one = lambda q: (q.first() or None)
        post, rx, med, prof = one(BlogPost.query), one(Prescription.query.filter(Prescription.number.isnot(None))), \
            one(Medicine.query), one(PrescriberProfile.query)
        users = [u.id for u in User.query.filter(User.email.in_(['demo.patient@example.com', 'demo.patient2@example.com',
                                                                 'demo.provider@example.com'])).all()]
        return {'post_id': [post.id] if post else [], 'rx_id': [rx.id] if rx else [], 'number': [rx.number] if rx else [],
                'medicine_id': [med.id] if med else [], 'profile_id': [prof.id] if prof else [], 'user_id': users}


def main():
    import logging
    logging.disable(logging.CRITICAL)
    from app import app
    _seed_prescription(app)
    _seed_blog(app)
    rules = sorted((r for r in app.url_map.iter_rules() if 'GET' in r.methods and not any(s in r.rule for s in SKIP)),
                   key=lambda r: r.rule)
    values = _values(app)
    for rule in rules:
        if not rule.arguments:
            print(rule.rule)
        elif '--all' in sys.argv:
            print('#', rule.rule, sorted(rule.arguments))
        else:
            args = sorted(rule.arguments)
            for combo in itertools.product(*(values.get(a, []) for a in args)):
                path = rule.rule
                for a, v in zip(args, combo):
                    path = re.sub(rf'<(?:[a-z]+:)?{a}>', str(v), path)
                print(path)


if __name__ == '__main__':
    main()
