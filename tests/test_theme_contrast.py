"""Colour tokens in static/css/site.css must stay legible and not harsh (see docs/research/color-theme.md)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_contrast", ROOT / "scripts" / "check_contrast.py")
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)
THEMES = cc.load()
PAIRS = [(t, fg, bg, need) for t in ("light", "dark", "dark-nojs")
         for pairs, need in ((cc.TEXT_PAIRS, 4.5), (cc.UI_PAIRS, 3.0)) for fg, bg in pairs]


@pytest.mark.parametrize("theme,fg,bg,need", PAIRS)
def test_pair_meets_minimum(theme, fg, bg, need):
    r = cc.ratio(THEMES[theme][fg], THEMES[theme][bg])
    assert r >= need, f"{theme}: {fg} on {bg} is {r:.2f}:1, needs {need}"


def test_no_pure_black_or_white_extremes():
    light, dark = THEMES["light"], THEMES["dark"]
    assert light["bg"] != (255, 255, 255), "light page background must not be pure white"
    assert light["text"] != (0, 0, 0), "light body text must not be pure black"
    assert dark["bg"] != (0, 0, 0), "dark page background must not be pure black"
    assert dark["text"] != (255, 255, 255), "dark body text must not be pure white"


def test_dark_text_is_not_glaring():
    # Halation guard: body text on the page background stays below about 15:1 in dark mode.
    assert cc.ratio(THEMES["dark"]["text"], THEMES["dark"]["bg"]) < 15


def test_dark_surfaces_step_lighter_with_elevation():
    d = THEMES["dark"]
    assert cc.lum(d["bg"]) < cc.lum(d["surface"]) < cc.lum(d["surface-2"]) < cc.lum(d["surface-raised"])


def test_nojs_dark_fallback_matches_dark_block():
    assert THEMES["dark"] == THEMES["dark-nojs"]
