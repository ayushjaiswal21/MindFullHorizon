"""Provider institution-wide analytics (small-cell suppressed aggregates)."""
from datetime import datetime, timedelta

from flask import render_template, session
from sqlalchemy import func

from decorators import login_required, role_required
from models import Assessment, BlogInsight, DigitalDetoxLog, Gamification, User, db
from utils.cache_utils import ANALYTICS_TTL, cached
from utils.timeutil import ist_today, utcnow

from . import provider_bp
from .helpers import all_institution_patients, institution_summary, min_group, normalize_institution_name


def _analytics_core(k):
    """Institution aggregates for the analytics page, all computed in SQL (no per-row Python loops). Cached by the caller."""
    pids = all_institution_patients().with_entities(User.id)
    total_patients = pids.count()
    since = ist_today() - timedelta(days=30)
    active_patients = db.session.query(func.count(func.distinct(DigitalDetoxLog.user_id))).filter(
        DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= since).scalar() or 0
    assessments_30_days = Assessment.query.filter(
        Assessment.user_id.in_(pids), Assessment.created_at >= utcnow() - timedelta(days=30)).count()
    stats = db.session.query(func.avg(Gamification.points), func.avg(Gamification.streak), func.count(Gamification.id)
                             ).filter(Gamification.user_id.in_(pids)).first()

    # one row per day: the day's log count and total hours are folded in Python from a few rows.
    # Deliberately does NOT aggregate DigitalDetoxLog.ai_score (the LLM-generated digital-detox
    # score): SYNTHESIS.md section 3(c) item c2 bans feeding that score into any aggregate, chart
    # or ranking, even with a caveat attached, because an institution-wide average of an
    # unvalidated per-student estimate loses the raw context that makes the estimate checkable.
    days = {}
    for day, n, hours in db.session.query(
            DigitalDetoxLog.date, func.count(), func.sum(DigitalDetoxLog.screen_time_hours)
    ).filter(DigitalDetoxLog.user_id.in_(pids), DigitalDetoxLog.date >= since).group_by(DigitalDetoxLog.date):
        days[day.strftime('%Y-%m-%d')] = {'count': n, 'hours': hours or 0}
    labels = [d for d in sorted(days) if days[d]['count'] >= k] if total_patients >= k else []
    screen = [round(days[day]['hours'] / days[day]['count'], 1) for day in labels]
    return {'total_patients': total_patients, 'active_patients': active_patients, 'assessments_30_days': assessments_30_days,
            'gamification_stats': tuple(stats), 'chart_labels': labels, 'screen_time_data': screen}


@provider_bp.route('/analytics')
@login_required
@role_required('provider')
def analytics():
    institution = session.get('user_institution') or ''

    # Get institutional analytics data
    institutional_data = institution_summary(institution)

    # Get recent blog insights
    recent_blog_insights = BlogInsight.query.order_by(BlogInsight.created_at.desc()).limit(10).all()

    # Institution-wide aggregates (not individual data); every figure below is hidden when fewer than K people stand behind it.
    k = min_group()
    cell = lambda n: None if n is not None and 0 < n < k else n
    core = cached('inst', ('analytics', normalize_institution_name(institution), k), ANALYTICS_TTL, lambda: _analytics_core(k))
    total_patients, active_patients, assessments_30_days, gamification_stats = (
        core['total_patients'], core['active_patients'], core['assessments_30_days'], core['gamification_stats'])
    chart_labels, screen_time_data = core['chart_labels'], core['screen_time_data']

    big = total_patients >= k  # below K nothing about the group is shown
    active_ok = big and (active_patients == 0 or active_patients >= k)
    analytics_data = {
        'institution': institution,
        'min_group': k,
        'total_patients': total_patients if big else None,
        'active_patients': active_patients if active_ok else None,
        'engagement_rate': round((active_patients / total_patients) * 100, 1) if active_ok and total_patients > 0 else None,
        'assessments_30_days': cell(assessments_30_days) if big else None,
        'avg_gamification_points': (round(gamification_stats[0], 1) if gamification_stats[0] else 0) if big else None,
        'avg_streak': (round(gamification_stats[1], 1) if gamification_stats[1] else 0) if big else None,
        'total_gamified_users': cell(gamification_stats[2]) if big else None,
        'chart_labels': chart_labels,
        'screen_time_data': screen_time_data,
        'blog_insights': recent_blog_insights,
        'institutional_data': institutional_data
    }

    return render_template('analytics.html',
                         user_name=session['user_name'],
                         analytics_data=analytics_data,
                         datetime=datetime)
