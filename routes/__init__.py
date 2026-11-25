# Import all blueprints to make them available when importing from routes package
from .auth import auth_bp
from .core import core_bp
from .patient import patient_bp
from . import patient_progress, patient_gamification  # noqa: F401  (attach routes and hooks to patient_bp)
from . import patient_safety_plan, patient_grounding_sleep, patient_reminders  # noqa: F401  (wellbeing tools on patient_bp)
from .provider import provider_bp
from .blog import blog_bp
from .assessment import bp as assessment_bp
from .mood import bp as mood_bp
from .chat import bp as chat_bp
from .seo import seo_bp
from .pages import pages_bp
from .ops import ops_bp
from .admin import admin_bp
from .rx_patient import rx_patient_bp
from .provider_meds import provider_meds_bp
from .provider_followups import provider_followups_bp

# List of all blueprints for easy registration
all_blueprints = [
    auth_bp,
    core_bp,
    patient_bp,
    provider_bp,
    blog_bp,
    assessment_bp,
    mood_bp,
    chat_bp,
    seo_bp,
    pages_bp,
    ops_bp,
    admin_bp,
    rx_patient_bp,
    provider_meds_bp,
    provider_followups_bp,
]