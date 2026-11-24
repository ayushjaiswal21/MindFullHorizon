"""Hooks for the gentle gamification card: the daily-visit award and the card data for templates.

Attached to the existing patient blueprint. No points for assessments or mood (utils/gamification.py).
"""
from flask import request, session

from routes.patient import patient_bp
from utils.gamification import award_daily_visit
from utils.gamification_card import card_context
from utils.timeutil import ist_today


@patient_bp.before_request
def _daily_visit():
    """First patient page load of the IST day earns the visit award once; the session flag skips later queries."""
    if request.method != 'GET' or session.get('user_role') != 'patient' or not session.get('user_id'):
        return None
    if request.path.startswith('/patient/api/'):
        return None
    today = ist_today().isoformat()
    if session.get('visit_day') != today:
        award_daily_visit(session['user_id'])  # logs and swallows its own failures
        session['visit_day'] = today
    return None


@patient_bp.app_context_processor
def _gamification_card():
    def gam_card():
        """Card data for the session patient; None for anyone else."""
        if session.get('user_role') != 'patient' or not session.get('user_id'):
            return None
        return card_context(session['user_id'])
    return {'gam_card': gam_card}
