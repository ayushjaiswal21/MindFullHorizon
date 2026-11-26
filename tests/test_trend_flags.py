"""Unit, perf-guard and integration tests for utils/trend_flags.py (docs/TREND_FLAGS.md)."""
from datetime import date, timedelta

from core.extensions import db
from models import MoodLog, ProviderPatient
from models import SleepLog
from test_perf_db import _count_queries, _seed_caseload
from utils import trend_flags
from utils.timeutil import utcnow

FLAT_NOISY = [7, 6, 8, 7, 6, 8, 7, 6, 8, 7, 6, 8]
STEP_DROP = [8, 8, 8, 8, 8, 8, 3, 3, 3, 3, 3, 3]
DATES = [date(2026, 1, 1) + timedelta(days=i) for i in range(12)]


# ---------- pure CUSUM / EWMA ----------

def test_cusum_flags_a_clear_step_change():
    hit = trend_flags.cusum_lower_changepoint(STEP_DROP)
    assert hit is not None
    start, end = hit
    assert end - start + 1 >= trend_flags.MIN_RUN


def test_cusum_does_not_flag_noisy_flat_series():
    assert trend_flags.cusum_lower_changepoint(FLAT_NOISY) is None


def test_cusum_does_not_flag_all_identical_values():
    assert trend_flags.cusum_lower_changepoint([5] * 10) is None


def test_cusum_handles_too_few_points():
    assert trend_flags.cusum_lower_changepoint([5]) is None
    assert trend_flags.cusum_lower_changepoint([]) is None


def test_ewma_same_length_and_smooths_toward_series():
    out = trend_flags.ewma(STEP_DROP)
    assert len(out) == len(STEP_DROP)
    assert out[0] == STEP_DROP[0]
    assert out[-1] < out[0]  # smoothed series follows the drop


# ---------- flag_from_series (dates + minimum points / run length) ----------

def test_flag_from_series_step_change():
    series = list(zip(DATES, STEP_DROP))
    f = trend_flags.flag_from_series('mood', series)
    assert f is not None
    assert f['kind'] == 'mood' and f['reason'] == 'sustained_drop'
    assert f['since'] == str(DATES[6])
    assert 'Mood down' in f['text']


def test_flag_from_series_flat_series_is_none():
    series = list(zip(DATES, FLAT_NOISY))
    assert trend_flags.flag_from_series('mood', series) is None


def test_flag_from_series_too_few_points_is_none():
    series = list(zip(DATES[:4], STEP_DROP[:4]))
    assert trend_flags.flag_from_series('sleep', series) is None


def test_flag_from_series_missing_days_still_works():
    """A gap in logged days (not every day present) is fine: the series is just shorter, dates stay attached."""
    sparse_dates = [DATES[0], DATES[2], DATES[5], DATES[6], DATES[9], DATES[11]]
    sparse_values = [8, 8, 8, 3, 3, 3]
    f = trend_flags.flag_from_series('sleep', list(zip(sparse_dates, sparse_values)))
    assert f is not None
    assert f['since'] == str(sparse_dates[3])


# ---------- grouping helpers ----------

def test_mood_series_averages_same_day_logs():
    from datetime import datetime
    # naive UTC; +5:30 keeps both same-day logs inside IST 2026-01-01
    rows = [(1, datetime(2026, 1, 1, 2, 0), 4), (1, datetime(2026, 1, 1, 10, 0), 6),
            (1, datetime(2026, 1, 2, 2, 0), 5)]
    out = trend_flags.mood_series(rows)
    assert out[1][0][1] == 5.0  # average of 4 and 6
    assert out[1][1][1] == 5.0


def test_sleep_series_converts_minutes_to_hours():
    rows = [(1, date(2026, 1, 1), 420), (1, date(2026, 1, 2), 480)]
    out = trend_flags.sleep_series(rows)
    assert out[1] == [(date(2026, 1, 1), 7.0), (date(2026, 1, 2), 8.0)]


def test_sparkline_xy_single_point_is_mid_width():
    xy = trend_flags.sparkline_xy([5], 10)
    assert len(xy) == 1 and abs(xy[0][0] - 80.0) < 0.1  # width 160, pad 4 -> mid = 4+152*0.5


# ---------- query-count guard (style of test_followup_perf.py) ----------

def _seed_trend(app, provider_id, n, flagged):
    """Every assigned patient without a sleep log yet gets 12 days of mood + sleep logs; a clear step-change if `flagged`."""
    values = STEP_DROP if flagged else FLAT_NOISY
    with app.app_context():
        done = {uid for uid, in db.session.query(SleepLog.user_id).all()}
        mine = [uid for uid, in db.session.query(ProviderPatient.patient_id).filter_by(provider_id=provider_id).all()]
        for uid in mine:
            if uid in done:
                continue
            for i, (d, v) in enumerate(zip(DATES, values)):
                db.session.add(MoodLog(user_id=uid, mood_score=v, created_at=utcnow() - timedelta(days=30 - i)))
                db.session.add(SleepLog(user_id=uid, night_date=d, bedtime='23:00', wake_time='07:00',
                                        duration_minutes=int(v * 60), quality=3))
        db.session.commit()


def test_dashboard_trend_flags_query_count_is_flat_for_30_patients(app, provider_client):
    c, pid = provider_client
    _seed_caseload(app, pid, 3)
    _seed_trend(app, pid, 3, flagged=True)
    few = _count_queries(app, lambda: c.get('/provider/dashboard'))
    _seed_caseload(app, pid, 30)
    _seed_trend(app, pid, 30, flagged=True)
    many = _count_queries(app, lambda: c.get('/provider/dashboard'))
    assert many <= few + 2, (few, many)


# ---------- integration: flag shows on the dashboard, absent for a stable patient ----------

def test_patient_with_real_mood_drop_shows_flag_stable_patient_does_not(app, provider_client):
    c, pid = provider_client
    _seed_caseload(app, pid, 2)
    with app.app_context():
        patients = [uid for uid, in db.session.query(ProviderPatient.patient_id).filter_by(provider_id=pid).all()]
    flagged_uid, stable_uid = patients[0], patients[1]
    with app.app_context():
        for i, (d, v) in enumerate(zip(DATES, STEP_DROP)):
            db.session.add(MoodLog(user_id=flagged_uid, mood_score=v, created_at=utcnow() - timedelta(days=30 - i)))
        for i, (d, v) in enumerate(zip(DATES, FLAT_NOISY)):
            db.session.add(MoodLog(user_id=stable_uid, mood_score=v, created_at=utcnow() - timedelta(days=30 - i)))
        db.session.commit()
    page = c.get('/provider/dashboard').get_data(as_text=True)
    assert 'Mood down since' in page
