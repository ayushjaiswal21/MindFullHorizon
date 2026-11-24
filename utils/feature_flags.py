"""Environment-driven feature flags. Read at call time so tests can monkeypatch the environment."""
import os


def _on(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def prescriptions_enabled():
    """Prescribing master switch. Default ON (owner decision, design C-11): safe because issuing needs a verified doctor
    and an empty catalogue blocks everything. Set ENABLE_PRESCRIPTIONS=0 to return 404 from the prescribing routes."""
    return _on('ENABLE_PRESCRIPTIONS', True)
