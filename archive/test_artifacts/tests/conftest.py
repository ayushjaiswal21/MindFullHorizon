import pytest
from app import app as flask_app

@pytest.fixture
def app():
    flask_app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for testing
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()
