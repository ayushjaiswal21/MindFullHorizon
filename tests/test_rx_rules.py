"""Pure prescribing rules (services/rx_rules.py) and prescription numbers (utils/rx_numbers.py)."""
from types import SimpleNamespace

import pytest

from services import rx_rules as R
from utils import rx_numbers

ENV = {"production": False, "allow_demo": False, "four_eyes": True}
NOW = object()


def med(**kw):
    base = dict(active=True, is_demo=False, schedule="none", is_controlled=False, list_verified_at=NOW,
                list_verified_by=None, updated_by=None, tpg_list="A")
    return SimpleNamespace(**(base | kw))


def test_allowed_lists_by_context():
    assert R.allowed_lists("first") == {"O", "A"}
    assert R.allowed_lists("follow_up") == R.allowed_lists("in_person") == {"O", "A", "B"}
    assert "C" not in R.allowed_lists("in_person")


@pytest.mark.parametrize("kw,ctx,code", [
    ({}, "first", None),
    ({"active": False}, "first", "medicine_inactive"),
    ({"list_verified_at": None}, "first", "medicine_unverified"),
    ({"list_verified_by": 5, "updated_by": 5}, "first", "medicine_unverified"),
    ({"list_verified_by": 6, "updated_by": 5}, "first", None),
    ({"tpg_list": "C"}, "in_person", "medicine_blocked_c"),
    ({"tpg_list": "B"}, "first", "medicine_needs_followup"),
    ({"tpg_list": "B"}, "follow_up", None),
    ({"schedule": "H1"}, "in_person", "medicine_controlled"),
    ({"schedule": "X", "is_controlled": True}, "in_person", "medicine_controlled"),
    ({"schedule": "NDPS", "is_controlled": True}, "in_person", "medicine_controlled"),
    ({"is_controlled": True}, "in_person", "medicine_controlled"),
    ({"schedule": "H"}, "first", None),
])
def test_medicine_blocked_reasons(kw, ctx, code):
    assert R.medicine_block_code(med(**kw), R.allowed_lists(ctx), ENV) == code


def test_demo_medicine_blocked_only_in_production():
    m = med(is_demo=True)
    assert R.medicine_block_code(m, {"A"}, ENV) is None
    assert R.medicine_block_code(m, {"A"}, ENV | {"production": True}) == "medicine_demo_blocked"
    assert R.medicine_block_code(m, {"A"}, ENV | {"production": True, "allow_demo": True}) is None


def test_four_eyes_off_accepts_same_admin():
    m = med(list_verified_by=5, updated_by=5)
    assert R.medicine_block_code(m, {"A"}, ENV | {"four_eyes": False}) is None


def test_item_limits_and_duration_cap():
    cfg = {"max_items": 2, "max_days_first": 14, "max_days_followup": 30}
    items = [{"line_no": i, "duration_days": 20} for i in (1, 2, 3)]
    codes = [(e["code"], e["item"]) for e in R.check_limits(items, "first", cfg)]
    assert ("too_many_items", None) in codes and ("duration_too_long", 1) in codes
    assert R.check_limits(items[:2], "follow_up", cfg) == []


def test_number_format_and_check_character():
    n = rx_numbers.new_number()
    assert len(n) == 18 and n.startswith("RX") and rx_numbers.is_valid_number(n)
    assert rx_numbers.is_valid_number(n.lower())
    bad = n[:-1] + ("0" if n[-1] != "0" else "1")
    assert not rx_numbers.is_valid_number(bad)
    assert not rx_numbers.is_valid_number("RX2611-SHORT") and not rx_numbers.is_valid_number(None)
    assert rx_numbers.mask_rx(n) == n[:7] + "*" * 8 + n[-3:]


def test_numbers_are_random():
    assert len({rx_numbers.new_number() for _ in range(50)}) == 50
