"""Score-change flags: arithmetic, band edges, one-query caseload read, caseload and report rendering (docs/FOLLOWUPS.md)."""
from datetime import timedelta

import pytest

from conftest import _login_as
from core.extensions import db
from models import Assessment, ProviderPatient
from utils import score_flags as sf
from utils.timeutil import utcnow


@pytest.mark.parametrize("kind,prev,latest,flag", [
    ("PHQ-9", 6, 11, "both"),       # exactly +5, and mild -> moderate
    ("PHQ-9", 10, 14, None),        # +4 inside moderate
    ("PHQ-9", 10, 15, "both"),
    ("PHQ-9", 0, 4, None),          # +4, same band
    ("PHQ-9", 1, 5, "band"),        # +4 but minimal -> mild
    ("PHQ-9", 4, 5, "band"),        # +1 across the 4/5 edge
    ("PHQ-9", 5, 9, None),          # top of mild, still mild
    ("PHQ-9", 9, 10, "band"),
    ("PHQ-9", 14, 15, "band"),
    ("PHQ-9", 19, 20, "band"),      # moderately severe -> severe
    ("PHQ-9", 20, 27, "rise"),      # +7 but already in the top band
    ("PHQ-9", 12, 7, None),         # falling never flags
    ("GAD-7", 9, 10, "band"),
    ("GAD-7", 14, 15, "band"),      # moderate -> severe
    ("GAD-7", 15, 21, "rise"),      # severe stays severe, +6
    ("GAD-7", 15, 20, "rise"),      # +5 in the top band
    ("GAD-7", 15, 19, None),
])
def test_compute_flag_arithmetic_and_band_edges(kind, prev, latest, flag):
    f = sf.compute_flag(kind, prev, latest)
    assert (f and f["reason"]) == flag, (kind, prev, latest, f)


def test_flag_wording_and_values():
    f = sf.compute_flag("PHQ-9", 6, 12)
    assert f["text"] == "Score up 6 since last screening (PHQ-9)" and f["delta"] == 6 and f["reason"] == "both"
    assert sf.compute_flag("GAD-7", 4, 5)["text"] == "Moved to a higher band since last screening (GAD-7)"
    assert sf.compute_flag("PHQ-9", None, 9) is None and sf.compute_flag("Mood", 1, 9) is None
    assert "diagnos" not in f["text"].lower()


def test_band_index_matches_scoring_tables():
    assert [sf.band_name("PHQ-9", s) for s in (0, 4, 5, 10, 15, 20, 27)] == [
        "minimal", "minimal", "mild", "moderate", "moderately severe", "severe", "severe"]
    assert [sf.band_name("GAD-7", s) for s in (4, 5, 10, 15, 21)] == ["minimal", "mild", "moderate", "severe", "severe"]


def test_sparkline_points_use_fixed_scale():
    pts = sf.sparkline_points([0, 27], "PHQ-9").split()
    assert len(pts) == 2 and float(pts[0].split(",")[1]) > float(pts[1].split(",")[1])  # higher score, smaller y
    assert sf.sparkline_points([5], "GAD-7").count(",") == 1 and len(sf.sparkline_xy([1, 2, 3], "GAD-7")) == 3


def _scores(app, uid, kind, scores, title=None):
    with app.app_context():
        now = utcnow()
        for i, s in enumerate(scores):
            db.session.add(Assessment(user_id=uid, assessment_type=title or kind, score=s,
                                      created_at=now - timedelta(days=len(scores) - i)))
        db.session.commit()


@pytest.fixture
def caseload(app, make_user):
    pid = make_user("provider")
    ids = {n: make_user("patient", name=n) for n in ("Up Six", "Flat", "Band Only", "Other Counsellor", "Long Title")}
    with app.app_context():
        for n, uid in ids.items():
            if n != "Other Counsellor":
                db.session.add(ProviderPatient(provider_id=pid, patient_id=uid, source="manual"))
        db.session.commit()
    _scores(app, ids["Up Six"], "PHQ-9", [3, 4, 10])
    _scores(app, ids["Flat"], "PHQ-9", [8, 9])
    _scores(app, ids["Flat"], "GAD-7", [2, 3])
    _scores(app, ids["Band Only"], "GAD-7", [4, 5])
    _scores(app, ids["Other Counsellor"], "PHQ-9", [1, 20])
    _scores(app, ids["Long Title"], "PHQ-9", [2], title="PHQ-9 Depression Screening")
    _scores(app, ids["Long Title"], "PHQ-9", [11], title="PHQ-9")  # same kind under two stored strings
    c = app.test_client()
    _login_as(c, app, pid)
    return dict(c=c, pid=pid, ids=ids)


def test_flags_for_provider_only_assigned_and_only_flagged(app, caseload):
    with app.app_context():
        flags = sf.flags_for_provider(caseload["pid"])
    ids = caseload["ids"]
    assert set(flags) == {ids["Up Six"], ids["Band Only"], ids["Long Title"]}
    assert flags[ids["Up Six"]][0]["delta"] == 6  # judged on the last two results, not the first
    assert flags[ids["Long Title"]][0]["latest"] == 11
    assert ids["Other Counsellor"] not in flags


def test_dashboard_shows_badge_and_filter_data(caseload):
    page = caseload["c"].get("/provider/dashboard").get_data(as_text=True)
    assert "Score up 6 since last screening (PHQ-9)" in page
    assert "Moved to a higher band since last screening (GAD-7)" in page
    assert 'id="caseloadFlagged"' in page and 'data-flag="1"' in page and 'data-flag="0"' in page
    assert "Other Counsellor" not in page


def test_report_has_sparkline_with_table_alternative(caseload):
    page = caseload["c"].get(f"/provider/wellness-report/{caseload['ids']['Up Six']}").get_data(as_text=True)
    assert "<polyline" in page and "Show PHQ-9 as a table" in page and "Score up 6 since last screening (PHQ-9)" in page
    assert "not a diagnosis" in page
    # the report of someone else's patient stays closed
    assert caseload["c"].get(f"/provider/wellness-report/{caseload['ids']['Other Counsellor']}").status_code == 404
