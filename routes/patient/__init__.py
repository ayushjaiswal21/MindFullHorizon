"""Patient blueprint, split by domain (dashboard/appointments, medication, wellness activities, goals,
assessment, journal, mood, misc). routes/patient_gamification.py, patient_progress.py, patient_safety_plan.py,
patient_grounding_sleep.py and patient_reminders.py attach more routes to this same `patient_bp` from outside
this package via `from routes.patient import patient_bp` (unchanged import path).
"""
from flask import Blueprint
from utils import idempotency as idem

AI_REQUEST_CAP = 8.0  # seconds a save request may wait for the model, then it uses the plain fallback

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')
patient_bp.register_error_handler(idem.InvalidKey, idem.handle_invalid_key)

from . import dashboard, medication, activities, goals, assessment_views, journal, mood_checkin, misc  # noqa: E402,F401
