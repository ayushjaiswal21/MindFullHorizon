"""Admin overview (design 5.4): one page and one JSON call, both built from `services.admin_dashboard.build`."""
from flask import g, jsonify, render_template

from decorators import admin_required
from extensions import db
from routes.admin import admin_bp
from routes.admin._inv import inst
from services import admin_dashboard
from services.ops_jobs import ensure_ops_daily_scheduled


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    ensure_ops_daily_scheduled()  # idempotent: makes sure the nightly job exists even if the worker was never seeded
    d = admin_dashboard.build(g.actor, inst())
    db.session.commit()
    return render_template('admin/dashboard.html', d=d, desk=bool(g.actor.is_pharmacy_desk), admin_name=g.actor.name,
                           institution=g.actor.institution)


@admin_bp.route('/api/dashboard')
@admin_required
def api_dashboard():
    return jsonify(success=True, **admin_dashboard.build(g.actor, inst()))
