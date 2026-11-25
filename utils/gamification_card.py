"""Read side of the gentle gamification card: streak, week dots, badges, level. No schema of its own.

Everything is computed from rows that already exist: PointsLedger refs 'visit:<ist-date>' (daily visit) and the
journal, breathing and goal rows. Nothing here reads an assessment or a mood score (docs/GAMIFICATION.md).
"""
from datetime import date, timedelta

from sqlalchemy import func, select

from core.extensions import db
from models import BreathingExerciseLog, Gamification, Goal, JournalEntry, PointsLedger
from utils.timeutil import ist_today, to_ist_date

LEVELS = [(0, 'Starting out'), (50, 'Settling in'), (150, 'Finding a rhythm'), (350, 'Steady'), (700, 'Established')]
LOOKBACK_DAYS = 400
STREAK_BADGES = [(3, 'streak_3', '3 day streak'), (7, 'streak_7', '7 day streak'), (30, 'streak_30', '30 day streak')]


def streak_from_days(days, today):
    """Consecutive IST days with a visit, ending today (or yesterday if today has no visit yet).

    One missed day per ISO week is forgiven; the missed day must sit between two visited days, so two misses in a
    row always end the streak. Forgiven days are not counted. Returns 0 when neither today nor yesterday has a visit.
    """
    day = today if today in days else today - timedelta(days=1)
    count, forgiven = 0, set()
    while True:
        if day in days:
            count += 1
        else:
            week = day.isocalendar()[:2]
            if (day - timedelta(days=1)) not in days or week in forgiven or count == 0:
                return count
            forgiven.add(week)
        day -= timedelta(days=1)


def week_dots(days, today):
    """Mon to Sun of the current IST week: [{'label': 'Mon', 'active': bool, 'today': bool}]."""
    monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(7):
        d = monday + timedelta(days=i)
        out.append({'label': d.strftime('%a'), 'active': d in days, 'today': d == today, 'future': d > today})
    return out


def level_for(points):
    """(level number, name, points still needed for the next level or None)."""
    idx = max(i for i, (need, _) in enumerate(LEVELS) if points >= need)
    nxt = LEVELS[idx + 1][0] - points if idx + 1 < len(LEVELS) else None
    return idx + 1, LEVELS[idx][1], nxt


def visit_days(user_id, today):
    """Set of IST dates with a daily-visit award, parsed from the ledger refs."""
    refs = db.session.scalars(select(PointsLedger.ref).where(
        PointsLedger.user_id == user_id, PointsLedger.activity_type == 'visit',
        PointsLedger.ref >= f'visit:{(today - timedelta(days=LOOKBACK_DAYS)).isoformat()}')).all()
    days = set()
    for ref in refs:
        try:
            days.add(date.fromisoformat(ref.split(':', 1)[1]))
        except (IndexError, ValueError):
            continue
    return days


def streak_badge_dates(days):
    """{3: date, 7: date, 30: date}: the first visited day on which the streak reached each length."""
    got = {}
    for d in sorted(days):
        n = streak_from_days({x for x in days if x <= d}, d)
        for need, _, _ in STREAK_BADGES:
            if n >= need and need not in got:
                got[need] = d
    return got


def _first_date(col, *where):
    ts = db.session.scalar(select(func.min(col)).where(*where))
    return to_ist_date(ts) if ts else None


def badges(user_id, days):
    """Factual badges in display order: [{'key','label','hint','date'}], date is None while not earned."""
    streak_dates = streak_badge_dates(days)
    goal_day = db.session.scalar(select(func.min(Goal.completed_date)).where(Goal.user_id == user_id, Goal.status == 'completed'))
    rows = [
        ('first_journal', 'First journal entry', 'Write a journal entry.', _first_date(JournalEntry.created_at, JournalEntry.user_id == user_id)),
        ('first_breathing', 'First breathing session', 'Log a breathing session.',
         _first_date(BreathingExerciseLog.created_at, BreathingExerciseLog.user_id == user_id)),
        ('first_goal', 'First goal completed', 'Mark a goal as completed.', goal_day),
    ]
    rows += [(key, label, f'Visit on {need} days in a row.', streak_dates.get(need)) for need, key, label in STREAK_BADGES]
    return [{'key': k, 'label': lab, 'hint': hint, 'date': d} for k, lab, hint, d in rows]


def card_context(user_id, today=None):
    today = today or ist_today()
    gam = db.session.scalar(select(Gamification).where(Gamification.user_id == user_id))
    points = (gam.points if gam else 0) or 0
    days = visit_days(user_id, today)
    streak = streak_from_days(days, today)
    level, level_name, to_next = level_for(points)
    items = badges(user_id, days)
    next_badge = next((b for b in items if not b['date']), None)
    return {
        'points': points, 'level': level, 'level_name': level_name, 'points_to_next_level': to_next,
        'streak': streak, 'dots': week_dots(days, today), 'badges': items, 'earned': [b for b in items if b['date']],
        'next_badge': next_badge,
        'restarted': streak <= 1 and len(days) > 1,  # earlier visits exist but the run was broken
    }
