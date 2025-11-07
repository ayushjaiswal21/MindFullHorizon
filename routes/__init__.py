# Import all blueprints to make them available when importing from routes package
from .auth import auth_bp
from .core import core_bp
from .patient import patient_bp
from .provider import provider_bp
from .blog import blog_bp
from .assessment import bp as assessment_bp
from .mood import bp as mood_bp
from .chat import bp as chat_bp

# List of all blueprints for easy registration
all_blueprints = [
    auth_bp,
    core_bp,
    patient_bp,
    provider_bp,
    blog_bp,
    assessment_bp,
    mood_bp,
    chat_bp
]