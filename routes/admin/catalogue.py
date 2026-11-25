"""Admin: medicine catalogue screens, JSON API, CSV import and export (design 4.9, 4.12, 5.4).

Any administrator may manage the catalogue (the pharmacy desk flag is not needed). The catalogue is shared by all
institutions; classification changes need a second administrator (four-eyes).
"""
from flask import Response, g, jsonify, render_template, request, url_for

from core.decorators import admin_required, prescriptions_required
from core.extensions import db, limiter
from routes.admin import admin_bp
from routes.admin._inv import page_errors
from services import catalogue as cat
from services import config
from services import inventory_csv as csvs
from services.errors import ServiceError
from services.http import json_body, service_errors
from utils.pagination import page_args

LISTS = [{'code': 'O', 'text': 'Any teleconsult. Over-the-counter type medicines.'},
         {'code': 'A', 'text': 'First consult by video, and repeat prescriptions.'},
         {'code': 'B', 'text': 'Follow-up consult only, or an in-person consult.'},
         {'code': 'C', 'text': 'Never by teleconsult. Blocked here. Choose C if unsure.'}]


def _config():
    return {'list': url_for('admin.api_catalogue_list'), 'create': url_for('admin.api_catalogue_create'),
            'import': url_for('admin.api_catalogue_import'), 'export': url_for('admin.catalogue_csv'),
            'template': url_for('admin.catalogue_template'), 'update_template': url_for('admin.api_catalogue_update', medicine_id=0)}


@admin_bp.route('/catalogue')
@prescriptions_required
@admin_required
def catalogue():
    page, per_page = page_args()
    rows, meta = cat.search(request.args.get('q'), request.args.get('list'), request.args.get('verified'),
                                  request.args.get('active'), page, per_page, me_id=g.actor.id)
    return render_template('admin/catalogue.html', rows=rows, meta=meta, filters=request.args.to_dict(),
                           four_eyes=config.four_eyes(), me_id=g.actor.id, config=_config())



@admin_bp.route('/catalogue/new', defaults={'medicine_id': None})
@admin_bp.route('/catalogue/<int:medicine_id>/edit')
@prescriptions_required
@admin_required
@page_errors
def catalogue_form(medicine_id):
    medicine = cat.serialize(cat.get(medicine_id), g.actor.id) if medicine_id else None
    return render_template('admin/catalogue_form.html', medicine=medicine, lists=LISTS, schedules=cat.SCHEDULES,
                           errors={}, four_eyes=config.four_eyes(), config=_config())


@admin_bp.route('/api/catalogue')
@prescriptions_required
@admin_required
def api_catalogue_list():
    page, per_page = page_args()
    rows, meta = cat.search(request.args.get('q'), request.args.get('list'), request.args.get('verified'),
                                  request.args.get('active'), page, per_page, me_id=g.actor.id)
    return jsonify(success=True, items=rows, meta=meta)


@admin_bp.route('/api/catalogue', methods=['POST'])
@prescriptions_required
@admin_required
@service_errors
def api_catalogue_create():
    m = cat.create(g.actor.id, json_body())
    db.session.commit()
    return jsonify(success=True, medicine=cat.serialize(m, g.actor.id)), 201


@admin_bp.route('/api/catalogue/<int:medicine_id>', methods=['PUT'])
@prescriptions_required
@admin_required
@service_errors
def api_catalogue_update(medicine_id):
    m = cat.update(g.actor.id, medicine_id, json_body())
    db.session.commit()
    return jsonify(success=True, medicine=cat.serialize(m, g.actor.id))


def _toggle(medicine_id, fn):
    m = fn(g.actor.id, medicine_id)
    db.session.commit()
    return jsonify(success=True, medicine=cat.serialize(m, g.actor.id))


@admin_bp.route('/api/catalogue/<int:medicine_id>/deactivate', methods=['POST'])
@prescriptions_required
@admin_required
@service_errors
def api_catalogue_deactivate(medicine_id):
    return _toggle(medicine_id, lambda a, m: cat.set_active(a, m, False))


@admin_bp.route('/api/catalogue/<int:medicine_id>/activate', methods=['POST'])
@prescriptions_required
@admin_required
@service_errors
def api_catalogue_activate(medicine_id):
    return _toggle(medicine_id, lambda a, m: cat.set_active(a, m, True))


@admin_bp.route('/api/catalogue/<int:medicine_id>/verify-list', methods=['POST'])
@prescriptions_required
@admin_required
@service_errors
def api_catalogue_verify_list(medicine_id):
    return _toggle(medicine_id, cat.verify_list)


def read_upload():
    """Bytes of the uploaded `file`, at most 1 MB (checked from the header first, then while reading)."""
    if (request.content_length or 0) > csvs.MAX_BYTES + 10_000:
        raise ServiceError('import_too_large', 413)
    f = request.files.get('file')
    if f is None:
        raise ServiceError('validation', 422, fields={'file': 'Choose a CSV file.'})
    return f.read(csvs.MAX_BYTES + 1)


def csv_response(text, filename):
    resp = Response(text, mimetype='text/csv')
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@admin_bp.route('/api/catalogue/import', methods=['POST'])
@limiter.limit('10 per hour')
@prescriptions_required
@admin_required
@service_errors
def api_catalogue_import():
    dry = request.form.get('dry_run', '1') not in ('0', 'false', 'no')
    result = csvs.import_catalogue(g.actor.id, read_upload(), dry_run=dry)
    db.session.rollback() if dry else db.session.commit()
    return jsonify(success=not result['errors'], **result), (200 if not result['errors'] else 422)


@admin_bp.route('/catalogue.csv')
@prescriptions_required
@admin_required
def catalogue_csv():
    return csv_response(csvs.catalogue_export(), 'medicines.csv')


@admin_bp.route('/catalogue/template.csv')
@prescriptions_required
@admin_required
def catalogue_template():
    return csv_response(csvs.catalogue_template(), 'medicines_template.csv')
