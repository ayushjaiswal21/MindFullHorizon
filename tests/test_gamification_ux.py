"""Gentle gamification: daily visit award, streak math (IST, weekly forgiveness), badges, the card, no points for scores."""
from datetime import date, datetime, timedelta

from extensions import db
from models import Gamification, JournalEntry, PointsLedger
from utils.gamification import award_daily_visit
from utils.gamification_card import badges, card_context, level_for, streak_from_days, streak_badge_dates, week_dots
from utils.timeutil import IST, ist_today

XHR = {"X-Requested-With": "XMLHttpRequest"}
MON = date(2026, 11, 23)  # a Monday


def days(*offsets, base=MON):
    return {base + timedelta(days=o) for o in offsets}


def points(app, uid):
    with app.app_context():
        g = Gamification.query.filter_by(user_id=uid).first()
        return g.points if g else 0


# ---- streak math ----

def test_streak_consecutive_days():
    assert streak_from_days(days(0, 1, 2), MON + timedelta(days=2)) == 3


def test_streak_today_not_visited_yet_counts_from_yesterday():
    assert streak_from_days(days(0, 1), MON + timedelta(days=2)) == 2


def test_streak_zero_when_yesterday_and_today_missing():
    assert streak_from_days(days(0, 1), MON + timedelta(days=3)) == 0


def test_one_missed_day_a_week_is_forgiven_and_not_counted():
    # Mon, Tue visited; Wed missed (forgiven); Thu visited
    assert streak_from_days(days(0, 1, 3), MON + timedelta(days=3)) == 3


def test_second_miss_in_the_same_week_breaks():
    # Mon visited, Tue missed, Wed visited, Thu missed, Fri visited: the Tue miss is the second forgiven in the walk
    assert streak_from_days(days(0, 2, 4), MON + timedelta(days=4)) == 2  # Fri, Wed, then Tue forgiven is used by Thu


def test_two_misses_in_a_row_break():
    assert streak_from_days(days(0, 1, 4), MON + timedelta(days=4)) == 1


def test_forgiveness_is_per_week():
    # week 1 misses Wed, week 2 misses Tue: one forgiven day in each week keeps the run alive
    d = days(0, 1, 3, 4, 5, 6, 7, 9)
    assert streak_from_days(d, MON + timedelta(days=9)) == 8


def test_streak_across_ist_midnight():
    # 18:29 UTC is 23:59 IST (same IST day); 18:31 UTC is 00:01 IST (next IST day)
    from utils.timeutil import to_ist_date
    assert to_ist_date(datetime(2026, 11, 23, 18, 29)) == date(2026, 11, 23)
    assert to_ist_date(datetime(2026, 11, 23, 18, 31)) == date(2026, 11, 24)


def test_streak_badge_dates():
    got = streak_badge_dates(days(0, 1, 2, 3, 4, 5, 6))
    assert got[3] == MON + timedelta(days=2) and got[7] == MON + timedelta(days=6) and 30 not in got


def test_week_dots_monday_to_sunday():
    dots = week_dots(days(0, 2), MON + timedelta(days=2))
    assert [d['label'] for d in dots] == ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    assert [d['active'] for d in dots] == [True, False, True, False, False, False, False]
    assert dots[2]['today'] and dots[3]['future']


def test_levels_are_neutral_and_monotonic():
    assert level_for(0)[:2] == (1, 'Starting out')
    assert level_for(150)[0] == 3 and level_for(10_000)[2] is None


# ---- awards ----

def test_daily_visit_awards_once_per_day(app, make_user):
    uid = make_user("patient")
    with app.app_context():
        award_daily_visit(uid)
        award_daily_visit(uid)
        refs = [r.ref for r in PointsLedger.query.filter_by(user_id=uid)]
    assert refs == [f"visit:{ist_today().isoformat()}"]
    assert points(app, uid) == 5


def test_first_patient_page_load_awards_the_visit_once(app, patient_client):
    c, uid = patient_client
    c.get("/patient/dashboard")
    c.get("/patient/dashboard")
    c.get("/patient/progress")
    assert points(app, uid) == 5


def test_api_calls_and_providers_earn_no_visit(app, patient_client, make_user, login):
    c, uid = patient_client
    c.get("/patient/api/progress")
    assert points(app, uid) == 0
    pid = make_user("provider")
    c2 = app.test_client()
    from conftest import _login_as
    _login_as(c2, app, pid)
    c2.get("/provider/dashboard")
    assert points(app, pid) == 0


def test_mood_and_assessment_award_nothing(app, patient_client):
    c, uid = patient_client
    c.post("/patient/api/save-mood", json={"mood": 7}, headers=XHR)
    c.post("/patient/api/save-assessment", json={"assessment_type": "PHQ-9", "responses": [1] * 9}, headers=XHR)
    with app.app_context():
        assert PointsLedger.query.filter_by(user_id=uid).count() == 0
    assert points(app, uid) == 0


def test_goal_progress_earns_once_per_goal_per_day(app, patient_client):
    from models import Goal
    c, uid = patient_client
    with app.app_context():
        g = Goal(user_id=uid, title="Walk", category="physical_health", start_date=ist_today(), target_value=10, current_value=0)
        db.session.add(g)
        db.session.commit()
        gid = g.id
    for v in (2, 4):
        assert c.put(f"/patient/api/goals/{gid}", json={"current_value": v}).status_code == 200
    assert points(app, uid) == 10
    c.put(f"/patient/api/goals/{gid}", json={"title": "Walk more"})  # a title edit is not progress
    assert points(app, uid) == 10


# ---- card and badges ----

def test_dashboard_and_profile_show_the_card(patient_client):
    c, _ = patient_client
    for url in ("/patient/dashboard", "/profile"):
        html = c.get(url).get_data(as_text=True)
        assert "Points never depend on your mood or screening scores" in html
        assert "One missed day a week is forgiven." in html and "Level 1: Starting out" in html
        assert 'aria-label="This week"' in html


def test_card_says_welcome_back_after_a_reset(app, make_user):
    uid = make_user("patient")
    today = ist_today()
    with app.app_context():
        for off in (10, 9, 0):
            db.session.add(PointsLedger(user_id=uid, ref=f"visit:{(today - timedelta(days=off)).isoformat()}", activity_type="visit", points=5))
        db.session.commit()
        ctx = card_context(uid, today)
    assert ctx["streak"] == 1 and ctx["restarted"]


def test_welcome_back_text_in_page(app, patient_client):
    c, uid = patient_client
    today = ist_today()
    with app.app_context():
        db.session.add(PointsLedger(user_id=uid, ref=f"visit:{(today - timedelta(days=12)).isoformat()}", activity_type="visit", points=5))
        db.session.commit()
    assert "Welcome back. A new streak starts today." in c.get("/patient/dashboard").get_data(as_text=True)


def test_badges_carry_the_date_they_were_earned(app, make_user):
    uid = make_user("patient")
    when = datetime(2026, 11, 20, 20, 0)  # 01:30 IST on the 21st
    with app.app_context():
        db.session.add(JournalEntry(user_id=uid, title="t", content="c", created_at=when))
        db.session.commit()
        got = {b["key"]: b["date"] for b in badges(uid, set())}
    assert got["first_journal"] == date(2026, 11, 21)
    assert got["first_breathing"] is None and got["streak_3"] is None


def test_card_context_ignores_scores(app, make_user):
    """The card reads no assessment or mood table: scores cannot move points, level or badges."""
    import inspect
    import utils.gamification_card as mod
    src = inspect.getsource(mod)
    assert "Assessment" not in src and "MoodLog" not in src
