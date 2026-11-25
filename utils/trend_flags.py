"""Deterministic trend/change-point flags for mood and sleep logs (docs/TREND_FLAGS.md).

No ML, no training data: this is Page's (1954) one-sided CUSUM control-chart method, the standard tool for
detecting a sustained shift in the mean of a noisy series (see Montgomery, "Introduction to Statistical
Quality Control", the standard reference for the k=0.5 / h=4 tuning used below, which targets a roughly
1-sigma sustained shift). An EWMA (Roberts, 1959) of the same series is also exposed, as a second published
method and for a smoother line on the chart; it is not required for the flag itself.

A flag fires only on a SUSTAINED downward shift (several points of accumulated evidence), never on one low
day. It describes a pattern in self-reported logs for a human to look at, not a diagnosis or a prediction
(see docs/TREND_FLAGS.md for the stated limitation). Output shape matches utils/score_flags.py's flags:
{'kind': 'mood'|'sleep', 'reason': 'sustained_drop', 'text': str, 'since': 'YYYY-MM-DD'}.
"""
from sqlalchemy import select

from core.extensions import db
from models import MoodLog, ProviderPatient
from models_wellbeing import SleepLog
from utils.timeutil import to_ist_date

MIN_POINTS = 6  # fewer points than this: not enough evidence either way
MIN_RUN = 3  # the shift must span at least this many points, not a single low day
K_SIGMA = 0.5  # CUSUM slack (Montgomery's standard tuning, targets a ~1-sigma shift)
H_SIGMA = 4.0  # CUSUM decision interval in units of sigma (Montgomery's standard tuning)
EWMA_LAMBDA = 0.3  # Roberts (1959); 0.2-0.3 is the usual range for a responsive-but-smoothed chart

LABEL = {'mood': 'mood', 'sleep': 'sleep'}


def ewma(values, lam=EWMA_LAMBDA):
    """Exponentially weighted moving average (Roberts, 1959); same length as `values`."""
    out, prev = [], None
    for v in values:
        prev = v if prev is None else lam * v + (1 - lam) * prev
        out.append(prev)
    return out


def _stats(values):
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return mean, var ** 0.5


def cusum_lower_changepoint(values, k=K_SIGMA, h=H_SIGMA):
    """Page's (1954) one-sided CUSUM for a sustained drop in the mean.

    Baseline mean is estimated from the earlier half of the series, sigma from the whole series. Returns
    (start_index, cross_index) of the run that crossed the lower decision limit, or None (including when the
    series has no variability at all, e.g. every value identical, since there is then no shift to detect).
    """
    n = len(values)
    if n < 2:
        return None
    mu0, _ = _stats(values[:max(2, n // 2)])
    _, sigma = _stats(values)
    if sigma == 0:
        return None
    allowance, limit = k * sigma, h * sigma
    c, start = 0.0, 0
    for i, v in enumerate(values):
        prev_c = c
        c = min(0.0, c + (v - mu0) + allowance)
        if prev_c == 0.0 and c < 0.0:
            start = i
        if c <= -limit:
            return start, i
    return None


def flag_from_series(kind, series):
    """series: sorted [(date, value), ...] for one patient and one signal -> flag dict or None."""
    values = [v for _, v in series]
    if len(values) < MIN_POINTS:
        return None
    hit = cusum_lower_changepoint(values)
    if not hit:
        return None
    start, end = hit
    if end - start + 1 < MIN_RUN:
        return None
    since = series[start][0]
    text = f'{LABEL[kind].capitalize()} down since {since}'  # short, like score_flags.py's badge text; the
    # "pattern not a diagnosis" caveat is given once, in the surrounding help text, not repeated per badge.
    return {'kind': kind, 'reason': 'sustained_drop', 'text': text, 'since': str(since)}


def mood_series(rows):
    """rows: (user_id, created_at, mood_score) -> {uid: [(ist_date, avg_score), ...] sorted} (days averaged)."""
    by_user_day = {}
    for uid, created_at, score in rows:
        by_user_day.setdefault(uid, {}).setdefault(to_ist_date(created_at), []).append(score)
    return {uid: sorted((d, sum(v) / len(v)) for d, v in days.items()) for uid, days in by_user_day.items()}


def sleep_series(rows):
    """rows: (user_id, night_date, duration_minutes) -> {uid: [(night_date, hours), ...] sorted}."""
    by_user = {}
    for uid, night_date, minutes in rows:
        by_user.setdefault(uid, []).append((night_date, minutes / 60.0))
    return {uid: sorted(v) for uid, v in by_user.items()}


def flags_for_provider(provider_id):
    """{patient_id: [flag, ...]} for the provider's assigned patients; patients without a flag are absent.

    Two queries total (one for mood, one for sleep), independent of caseload size, matching
    utils/score_flags.py's one-query-per-signal pattern.
    """
    mine = select(ProviderPatient.patient_id).where(ProviderPatient.provider_id == provider_id)
    mood_rows = db.session.execute(select(MoodLog.user_id, MoodLog.created_at, MoodLog.mood_score)
                                    .where(MoodLog.user_id.in_(mine))).all()
    sleep_rows = db.session.execute(select(SleepLog.user_id, SleepLog.night_date, SleepLog.duration_minutes)
                                     .where(SleepLog.user_id.in_(mine))).all()
    out = {}
    for uid, series in mood_series(mood_rows).items():
        f = flag_from_series('mood', series)
        if f:
            out.setdefault(uid, []).append(f)
    for uid, series in sleep_series(sleep_rows).items():
        f = flag_from_series('sleep', series)
        if f:
            out.setdefault(uid, []).append(f)
    return out


def history_for_patient(patient_id, limit=60):
    """{'mood': [(date, value), ...], 'sleep': [...]} for one patient, oldest first, capped at `limit` per kind."""
    mood_rows = db.session.execute(select(MoodLog.user_id, MoodLog.created_at, MoodLog.mood_score)
                                    .where(MoodLog.user_id == patient_id)
                                    .order_by(MoodLog.created_at.desc()).limit(limit)).all()
    sleep_rows = db.session.execute(select(SleepLog.user_id, SleepLog.night_date, SleepLog.duration_minutes)
                                     .where(SleepLog.user_id == patient_id)
                                     .order_by(SleepLog.night_date.desc()).limit(limit)).all()
    out = {}
    mood = mood_series(mood_rows).get(patient_id)
    if mood:
        out['mood'] = mood
    sleep = sleep_series(sleep_rows).get(patient_id)
    if sleep:
        out['sleep'] = sleep
    return out


def sparkline_xy(values, vmax, width=160, height=48, pad=4):
    """[(x, y)] SVG coordinates on a fixed 0..vmax scale (a 1-point series sits mid-width)."""
    n = len(values)
    return [(pad + (width - 2 * pad) * (i / (n - 1) if n > 1 else 0.5),
             height - pad - (height - 2 * pad) * min(max(v, 0), vmax) / vmax) for i, v in enumerate(values)]
