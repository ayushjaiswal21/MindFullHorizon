"""Time helpers. Stored timestamps are naive UTC; "today" for patients is the IST calendar day.

Convention (docs/MIGRATIONS.md): DateTime columns hold naive UTC (`utcnow()`), Date columns that mean
"a patient's day" (detox log date, medication log_date, gamification last_activity) hold the IST date.
"""
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo('Asia/Kolkata')
except Exception:  # no tz database (Windows without the tzdata package); India has had no DST since 1945
    IST = timezone(timedelta(hours=5, minutes=30), 'IST')


def utcnow():
    """Naive UTC now, the format of every stored DateTime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ist_now():
    """Naive IST wall-clock now (appointment date/time strings are IST wall-clock)."""
    return datetime.now(IST).replace(tzinfo=None)


def ist_today():
    return datetime.now(IST).date()


def to_ist_date(naive_utc):
    """IST calendar date of a stored (naive UTC) timestamp."""
    return naive_utc.replace(tzinfo=timezone.utc).astimezone(IST).date()


def ist_day_bounds(day=None):
    """[start, end) of an IST day as naive UTC datetimes, for filtering stored timestamps."""
    day = day or ist_today()
    start = datetime(day.year, day.month, day.day, tzinfo=IST).astimezone(timezone.utc).replace(tzinfo=None)
    return start, start + timedelta(days=1)
