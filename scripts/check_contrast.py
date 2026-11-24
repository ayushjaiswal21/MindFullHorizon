"""Print WCAG 2.x contrast ratios for the colour tokens in static/css/site.css (stdlib only).

Usage: python scripts/check_contrast.py   (exit code 1 if any required pair fails)
Pairs are (foreground, background, minimum): 4.5 for text, 3.0 for focus ring and meaningful borders.
"""
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "site.css"
BLOCKS = {
    "light": r":root\s*\{",
    "dark": r':root\[data-theme="dark"\]\s*\{',
    "dark-nojs": r":root:not\(\[data-theme\]\)\s*\{",
}
STATUS = ("danger", "warning", "success", "info")
# Text pairs need 4.5:1; "ui" pairs (focus ring, input borders, status edges) need 3:1.
TEXT_PAIRS = [("text", "bg"), ("text", "surface"), ("text", "surface-2"),
              ("text-muted", "bg"), ("text-muted", "surface"), ("text-muted", "surface-2"),
              ("primary-contrast", "primary"), ("primary-contrast", "primary-hover"),
              ("primary", "bg"), ("primary", "surface"), ("primary-hover", "surface"),
              ("on-danger", "danger"), ("crisis-text", "crisis-bg"), ("text", "primary-soft")]
TEXT_PAIRS += [(s, "surface") for s in STATUS] + [(s, "bg") for s in STATUS]
TEXT_PAIRS += [(s, s + "-soft") for s in STATUS]
UI_PAIRS = [("focus", "bg"), ("focus", "surface"), ("focus", "surface-2"), ("input-border", "surface"),
            ("input-border", "bg")] + [(s, "surface") for s in STATUS]


def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(rgb):
    f = lambda c: (c / 255 / 12.92) if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def block_text(css, opener):
    m = re.search(opener, css)
    if not m:
        raise SystemExit("token block not found: " + opener)
    depth, i = 1, m.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return css[m.end():i - 1]


def parse(css, theme):
    """Return {token: (r,g,b)} for one theme; dark inherits anything it does not set from light."""
    body = block_text(css, BLOCKS[theme])
    raw = dict(re.findall(r"--([\w-]+):\s*([^;]+);", body))
    return raw


def resolve(light_raw, raw):
    toks = {}
    for k, v in {**light_raw, **raw}.items():
        v = v.strip()
        if re.fullmatch(r"#[0-9a-fA-F]{3,6}", v):
            toks[k] = hex_rgb(v)
    toks.setdefault("surface-raised", toks["surface"])
    for s in ("primary",) + STATUS:  # --X-soft is color-mix(in srgb, var(--X) 10%, var(--surface))
        c, bg = toks[s], toks["surface"]
        toks[s + "-soft"] = tuple(round(c[i] * 0.1 + bg[i] * 0.9) for i in range(3))
    return toks


def load(css=None):
    css = css or CSS.read_text(encoding="utf-8")
    light_raw = parse(css, "light")
    return {t: resolve(light_raw, parse(css, t)) for t in ("light", "dark", "dark-nojs")}


def evaluate(themes):
    rows = []
    for theme, toks in themes.items():
        for pairs, need in ((TEXT_PAIRS, 4.5), (UI_PAIRS, 3.0)):
            for fg, bg in pairs:
                r = ratio(toks[fg], toks[bg])
                rows.append((theme, fg, bg, r, need))
    return rows


def main():
    rows = evaluate(load())
    bad = 0
    for theme, fg, bg, r, need in rows:
        ok = r >= need
        bad += not ok
        print(f"{theme:9} {fg:17} on {bg:13} {r:6.2f}:1  need {need:<4} {'ok' if ok else 'FAIL'}")
    print(f"\n{len(rows)} pairs, {bad} failing; lowest per theme:")
    for t in ("light", "dark"):
        worst = min((x for x in rows if x[0] == t), key=lambda x: x[3] - x[4])
        print(f"  {t}: {worst[1]} on {worst[2]} = {worst[3]:.2f}:1 (need {worst[4]})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
