"""Annual report: page, print view and CSV (design 5.4). Aggregates with K = MIN_AGGREGATE_GROUP suppression."""
from flask import Response, g, render_template

from core.decorators import admin_required
from core.extensions import db
from routes.admin import admin_bp
from routes.admin._inv import arg_int, inst
from services import annual_report
from utils.audit import audit as write_audit
from utils.timeutil import ist_today


def _report(fmt):
    years = [ist_today().year - i for i in range(5)]
    year = arg_int('year', years[0])
    year = year if year in years else years[0]
    report = annual_report.build(inst(), year)
    report['institution'] = g.actor.institution  # as typed, for the heading
    write_audit(g.actor.id, 'export_annual_report', 'report', None, year=year, fmt=fmt)
    db.session.commit()
    return report, years


@admin_bp.route('/annual-report')
@admin_required
def annual():
    report, years = _report('page')
    return render_template('admin/annual.html', report=report, years=years)


@admin_bp.route('/annual-report.csv')
@admin_required
def annual_csv():
    report, _ = _report('csv')
    resp = Response(annual_report.to_csv_text(report), mimetype='text/csv')
    resp.headers['Content-Disposition'] = f'attachment; filename="annual-report-{report["year"]}.csv"'
    resp.headers['Cache-Control'] = 'no-store'
    return resp
