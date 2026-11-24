"""Server-side input bounds shared by routes (mirror them in client JS/HTML)."""

MIN_DURATION_MINUTES = 1
MAX_DURATION_MINUTES = 180


def parse_duration(value):
    """Whole minutes in [1, 180] as an int, else None."""
    try:
        minutes = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return minutes if MIN_DURATION_MINUTES <= minutes <= MAX_DURATION_MINUTES else None
