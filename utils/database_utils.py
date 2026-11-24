import os
from flask import current_app
from extensions import db
from sqlalchemy.exc import SQLAlchemyError

def check_database():
    """Check if the database is properly initialized and accessible."""
    try:
        # Test database connection
        with current_app.app_context():
            # Check if users table exists
            from models import User
            User.query.first()
            current_app.logger.info("Database connection successful")
            return True
    except Exception as e:
        current_app.logger.error(f"Database connection error: {str(e)}", exc_info=True)
        return False

def init_db():
    """Dev/test bootstrap: create_all. Production (and `SKIP_CREATE_ALL=1`, needed for the first
    `flask db upgrade` on an empty DB) leaves the schema to Alembic migrations."""
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('SKIP_CREATE_ALL') == '1':
        current_app.logger.warning("create_all skipped; run `flask db upgrade` (see docs/MIGRATIONS.md)")
        return False
    try:
        with current_app.app_context():
            db.create_all()
            current_app.logger.info("Database tables created successfully")
            return True
    except Exception as e:
        current_app.logger.error(f"Database initialization error: {str(e)}", exc_info=True)
        return False
