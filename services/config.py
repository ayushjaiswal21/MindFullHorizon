"""Typed, clamped environment getters for the clinical features. Read at call time; a bad value falls back to the default."""
import os


def _int(name, default, low, high):
    try:
        value = int(os.getenv(name, '').strip() or default)
    except ValueError:
        return default
    return max(low, min(high, value))


def _flag(name, default):
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in ('1', 'true', 'yes', 'on')


def review_days():
    return _int('PRESCRIBER_REVIEW_DAYS', 365, 30, 1095)


def rx_expiry_days():
    return _int('RX_EXPIRY_DAYS', 30, 1, 90)


def rx_max_items():
    return _int('RX_MAX_ITEMS', 6, 1, 20)


def rx_max_days_first():
    return _int('RX_MAX_DAYS_FIRST', 14, 1, 90)


def rx_max_days_followup():
    return _int('RX_MAX_DAYS_FOLLOWUP', 30, 1, 90)


def rx_consult_window_hours():
    return _int('RX_CONSULT_WINDOW_HOURS', 24, 1, 168)


def erx_consent_version():
    return os.getenv('ERX_CONSENT_VERSION', '').strip()[:20] or '2026-11'


def four_eyes():
    return _flag('CATALOGUE_FOUR_EYES', True)


def min_shelf_days():
    return _int('INVENTORY_MIN_SHELF_DAYS', 0, 0, 365)


def near_expiry_days():
    return _int('INVENTORY_NEAR_EXPIRY_DAYS', 60, 1, 365)


def allow_demo_data():
    return _flag('ALLOW_DEMO_DATA', False)


def in_production():
    return os.getenv('FLASK_ENV', '').strip().lower() == 'production'


def min_group():
    return _int('MIN_AGGREGATE_GROUP', 5, 1, 1000)


def crisis_escalate_minutes():
    return _int('CRISIS_ESCALATE_MINUTES', 15, 0, 1440)
