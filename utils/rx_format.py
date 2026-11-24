"""Display helpers for prescription pages. Stored times are naive UTC; patients read them in IST."""
from datetime import datetime, timezone

from utils.timeutil import IST


def to_ist(value):
    """A datetime or an ISO 8601 string (UTC, with or without Z) as an aware IST datetime, or None."""
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST)


def rx_date(value):
    d = to_ist(value)
    return d.strftime('%d %b %Y') if d else 'n/a'


def rx_datetime(value):
    d = to_ist(value)
    return d.strftime('%d %b %Y, %H:%M IST') if d else 'n/a'
