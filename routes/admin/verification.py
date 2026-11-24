"""Doctor verification queue and decisions (design 2, 5.4). A person checks the register; the app does not."""
from flask import g, jsonify, render_template, request

from decorators import admin_required
from extensions import db
from routes.admin import admin_bp
from routes.admin._inv import inst, page_errors
from services import prescriber
from services.http import json_body, service_errors
from utils.pagination import page_args

TABS = ('pending', 'verified', 'suspended', 'rejected')
REGISTER_URL = 'https://www.nmc.org.in/information-desk/indian-medical-register/'
BLACKLIST_URL = 'https://www.nmc.org.in/information-desk/indian-medical-register/black-list-doctors/'
CHECKLIST = [
    {'key': 'register_found', 'text': 'I searched the Indian Medical Register by registration number and found the entry.'},
    {'key': 'details_match', 'text': "The entry's name matches the doctor's account name, the year matches, and the State Medical Council matches."},
    {'key': 'not_removed', 'text': 'The doctor is not on the NMC removed-doctors list (if in doubt I asked the State Medical Council).'},
    {'key': 'modern_medicine', 'text': 'The registration is for modern medicine (not AYUSH).'},
    {'key': 'works_here', 'text': 'The doctor works with this institution (institutional email or staff ID).'},
]


@admin_bp.route('/verification')
@admin_required
@page_errors
def verification():
    tab = request.args.get('tab') if request.args.get('tab') in TABS else 'pending'
    page, per_page = page_args()
    rows, meta = prescriber.queue(inst(), tab, page, per_page)
    return render_template('admin/verification.html', tab=tab, counts=prescriber.counts(inst()), rows=rows, meta=meta)


@admin_bp.route('/verification/<int:profile_id>')
@admin_required
@page_errors
def verification_detail(profile_id):
    p, user = prescriber.get_for_admin(profile_id, g.actor.id)
    return render_template('admin/verification_detail.html', p=prescriber.item(p, user, include_notes=True),
                           register_url=REGISTER_URL, blacklist_url=BLACKLIST_URL, checklist=CHECKLIST,
                           actions=prescriber.allowed_actions(p))


@admin_bp.route('/api/verification')
@admin_required
@service_errors
def api_verification_list():
    status = request.args.get('status') if request.args.get('status') in TABS else None
    page, per_page = page_args()
    rows, meta = prescriber.queue(inst(), status, page, per_page)
    return jsonify(success=True, items=rows, meta=meta)


def _decide(profile_id, action):
    body = json_body()
    note = body.get('note')
    if action in ('verify', 'reinstate'):
        p = getattr(prescriber, action)(profile_id, g.actor.id, body.get('checks'), note)
    else:
        p = getattr(prescriber, action)(profile_id, g.actor.id, note)
    db.session.commit()
    return jsonify(success=True, status=p.status, state=prescriber.state_of(p),
                   verified_at=p.verified_at.isoformat() + 'Z' if p.verified_at else None)


def _register(action):
    @admin_required
    @service_errors
    def view(profile_id):
        return _decide(profile_id, action)
    view.__name__ = f'api_verification_{action}'
    admin_bp.add_url_rule(f'/api/verification/<int:profile_id>/{action}', view_func=view, methods=['POST'])


for _action in ('verify', 'reject', 'suspend', 'reinstate'):
    _register(_action)
