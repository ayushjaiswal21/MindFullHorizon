"""Flask extensions initialization."""
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_session import Session
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
flask_session = Session()
compress = Compress()
csrf = CSRFProtect()
# Campus networks share one IP, so keep the global limit generous; auth routes add stricter ones.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["2000 per day", "300 per hour", "60 per minute"],
    storage_uri="memory://" if os.getenv('FLASK_ENV') == 'development' else None,
    strategy="fixed-window",
    headers_enabled=True,
    retry_after="http-date",
)

def init_extensions(app):
    """Initialize Flask extensions in the correct order."""
    # Ensure instance directory exists
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)
    
    # Initialize SQLAlchemy first
    db.init_app(app)
    
    # Then initialize Flask-Migrate
    migrate.init_app(app, db)
    
    # Initialize session after database
    if not os.path.exists(app.config['SESSION_FILE_DIR']):
        os.makedirs(app.config['SESSION_FILE_DIR'])
    flask_session.init_app(app)
    
    # Initialize security features - CSRF is initialized in app.py
    # csrf.init_app(app)  # Already initialized in app.py
    
    # Initialize compression last
    compress.init_app(app)
