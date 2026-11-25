"""Print every GET rule without URL parameters, one per line: path<TAB>endpoint. Used by specs/layout_sweep.mjs.

    python tools/e2e/list_routes.py            (run from the project root with the app's env, e.g. DATABASE_URL)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app import app  # noqa: E402

SKIP = ('static', 'logout', 'download', 'export', 'delete')  # endpoints that change state or return files

for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    if 'GET' not in rule.methods or rule.arguments:
        continue
    if rule.endpoint == 'static' or rule.endpoint.endswith('.static') or any(s in rule.endpoint for s in SKIP):
        continue
    print(f'{rule.rule}\t{rule.endpoint}')

# Representative parameterised pages built from rows that exist: "PARAM<TAB>path" (the spec tries each as every role).
with app.app_context():
    from models import BlogPost, Prescription, PrescriberProfile, Medicine, User, Appointment
    for post in BlogPost.query.limit(1):
        print(f'PARAM\t/blog/{post.id}\nPARAM\t/blog/{post.id}/edit')
    for rx in Prescription.query.limit(2):
        print(f'PARAM\t/patient/prescriptions/{rx.id}\nPARAM\t/patient/prescriptions/{rx.id}/print')
        print(f'PARAM\t/provider/prescriptions/{rx.id}\nPARAM\t/provider/prescriptions/{rx.id}/print')
        print(f'PARAM\t/admin/dispensing/{rx.id}\nPARAM\t/admin/dispensing/{rx.id}/print')
        if rx.number:
            print(f'PARAM\t/rx/{rx.number}')
    for prof in PrescriberProfile.query.limit(1):
        print(f'PARAM\t/admin/verification/{prof.id}')
    for med in Medicine.query.limit(1):
        print(f'PARAM\t/admin/catalogue/{med.id}/edit')
    print('PARAM\t/admin/catalogue/new')
    for appt in Appointment.query.limit(1):
        print(f'PARAM\t/provider/wellness-report/{appt.user_id}\nPARAM\t/provider/telehealth/{appt.user_id}')
        print(f'PARAM\t/telehealth_session/{appt.user_id}')
