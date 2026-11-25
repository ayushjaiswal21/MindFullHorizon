"""Sleep log: validation, the 14-day series and the inline-SVG bar geometry. Private to the student, no points, no score."""
import re
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import SleepLog
from utils import idempotency as idem
from utils.timeutil import ist_today

TIME_RE = re.compile(r'([01]\d|2[0-3]):[0-5]\d')
CTRL_RE = re.compile(r'[\x00-\x1f\x7f]+')
MAX_NOTE, MAX_HOURS, WINDOW_DAYS, BACK_DAYS = 200, 16, 14, 30
QUALITY = {1: 'Very poor', 2: 'Poor', 3: 'Okay', 4: 'Good', 5: 'Very good'}


class SleepError(ValueError):
    """A plain message the student can read."""


def _minutes(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def parse(form):
    """Validated dict for a SleepLog, or raises SleepError."""
    bed, wake = (form.get('bedtime') or '').strip(), (form.get('wake_time') or '').strip()
    if not (TIME_RE.fullmatch(bed) and TIME_RE.fullmatch(wake)):
        raise SleepError('Enter bedtime and wake time as hours and minutes, for example 23:30.')
    try:
        night = date.fromisoformat((form.get('night_date') or '').strip() or ist_today().isoformat())
    except ValueError:
        raise SleepError('Enter the date you woke up.')
    today = ist_today()
    if night > today or night < today - timedelta(days=BACK_DAYS):
        raise SleepError(f'Choose a date from the last {BACK_DAYS} days, up to today.')
    try:
        quality = int(form.get('quality') or 0)
    except ValueError:
        quality = 0
    if quality not in QUALITY:
        raise SleepError('Choose how well you slept, from 1 to 5.')
    minutes = (_minutes(wake) - _minutes(bed)) % 1440  # bedtime before midnight and waking after it is the usual case
    if minutes == 0 or minutes > MAX_HOURS * 60:
        raise SleepError(f'That is 0 or more than {MAX_HOURS} hours. Please check bedtime and wake time.')
    note = CTRL_RE.sub(' ', form.get('note') or '').strip()
    if len(note) > MAX_NOTE:
        raise SleepError(f'The note can be up to {MAX_NOTE} characters.')
    return dict(night_date=night, bedtime=bed, wake_time=wake, duration_minutes=minutes, quality=quality, note=note or None)


def add(user_id, data, key=None):
    """(row, created). A replayed key returns the first row; a second entry for the same night raises SleepError."""
    row, created = None, False
    try:
        row, created = idem.add_once(SleepLog, SleepLog(user_id=user_id, client_request_id=key, **data), key)
    except IntegrityError:
        db.session.rollback()
        raise SleepError('You already logged that night. Delete the entry first if you want to log it again.')
    return row, created


def delete(user_id, log_id):
    row = SleepLog.query.filter_by(id=log_id, user_id=user_id).first()
    if row:
        db.session.delete(row)
        db.session.commit()
    return bool(row)


def hm(minutes):
    return f'{minutes // 60} h {minutes % 60:02d} min'


def summary(user_id):
    """{'rows': 14 newest-first days, 'bars': svg geometry, 'average': text or None, 'count': int}."""
    today = ist_today()
    first = today - timedelta(days=WINDOW_DAYS - 1)
    logs = {r.night_date: r for r in SleepLog.query.filter(SleepLog.user_id == user_id, SleepLog.night_date >= first,
                                                           SleepLog.night_date <= today)}
    days = [first + timedelta(days=i) for i in range(WINDOW_DAYS)]
    top = max([10] + [-(-r.duration_minutes // 60) for r in logs.values()])  # axis top in whole hours, at least 10
    w, h, left, bottom, slot = 420, 170, 28, 22, (420 - 28) / WINDOW_DAYS
    bars = []
    for i, d in enumerate(days):
        r = logs.get(d)
        bh = (h - bottom - 8) * (r.duration_minutes / 60) / top if r else 0
        bars.append(dict(x=round(left + i * slot + slot * 0.18, 1), w=round(slot * 0.64, 1), y=round(h - bottom - bh, 1),
                         h=round(bh, 1), label=d.strftime('%d'), has=bool(r), tx=round(left + i * slot + slot / 2, 1),
                         title=f"{d.strftime('%d %b')}: {hm(r.duration_minutes)}" if r else f"{d.strftime('%d %b')}: no entry"))
    grid = [dict(y=round(h - bottom - (h - bottom - 8) * v / top, 1), label=v) for v in range(0, top + 1, 2 if top <= 12 else 4)]
    mins = [r.duration_minutes for r in logs.values()]
    rows = [dict(day=d, log=logs.get(d), hours=hm(logs[d].duration_minutes) if d in logs else None) for d in reversed(days)]
    return dict(rows=rows, bars=bars, grid=grid, w=w, h=h, left=left, count=len(mins),
                average=hm(round(sum(mins) / len(mins))) if mins else None)
