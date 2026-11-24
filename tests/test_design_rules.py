"""Design and copy rules from docs/DESIGN_SYSTEM.md, enforced on source files.

Each rule is its own parametrised test so progress is visible per category. A failure prints findings grouped
by file (file:line: snippet). Do not weaken a rule to make it pass; fix the file instead.
"""
import os
import re
from collections import defaultdict

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'gen', 'vendor', 'vendors', 'node_modules', 'lib', '__pycache__', 'uploads', 'webassets-cache', '.webassets-cache'}


def _walk(rel_dir, exts, recursive=True):
    base = os.path.join(ROOT, rel_dir)
    out = []
    if not os.path.isdir(base):
        return out
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(exts) and not fn.endswith('.min.js'):
                out.append(os.path.join(dirpath, fn))
        if not recursive:
            break
    return out


def _files(kind):
    if kind == 'templates':
        return _walk('templates', ('.html',))
    if kind == 'js':
        return _walk('static/js', ('.js',))
    if kind == 'css':
        return [p for p in (os.path.join(ROOT, 'static/css', n) for n in ('site.css', 'components.css', 'print.css')) if os.path.exists(p)]
    if kind == 'prompts':
        return _walk('ai_prompts', ('',))
    if kind == 'py':
        return _walk('routes', ('.py',), False) + _walk('ai', ('.py',), False) + _walk('utils', ('.py',), False)
    raise KeyError(kind)


def _read(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except (UnicodeDecodeError, OSError):
        return ''


def _rel(path):
    return os.path.relpath(path, ROOT).replace('\\', '/')


def _scan_lines(paths, regex, flags=0, label=None):
    """{relative path: [(line number, snippet)]} for every line matching regex."""
    rx = re.compile(regex, flags)
    found = defaultdict(list)
    for path in paths:
        for n, line in enumerate(_read(path).splitlines(), 1):
            m = rx.search(line)
            if m:
                snippet = line.strip()
                if len(snippet) > 110:
                    start = max(0, m.start() - 40)
                    snippet = '...' + line[start:start + 100].strip()
                found[_rel(path)].append((n, label or snippet))
    return found


def _scan_tags(paths, tag_regex, must_have):
    """Multi-line aware: opening tags matching tag_regex whose text also matches must_have."""
    tag_rx, need = re.compile(tag_regex, re.S | re.I), re.compile(must_have)
    found = defaultdict(list)
    for path in paths:
        text = _read(path)
        for m in tag_rx.finditer(text):
            if need.search(m.group(0)):
                line = text.count('\n', 0, m.start()) + 1
                found[_rel(path)].append((line, ' '.join(m.group(0).split())[:110]))
    return found


def _merge(*results):
    merged = defaultdict(list)
    for res in results:
        for k, v in res.items():
            merged[k].extend(v)
    return merged


def _report(rule, found):
    if not found:
        return
    lines = [f'{rule}: {sum(len(v) for v in found.values())} finding(s) in {len(found)} file(s)']
    for path in sorted(found):
        hits = found[path]
        lines.append(f'  {path} ({len(hits)})')
        for n, snip in hits[:5]:
            lines.append(f'      {n}: {snip}')
        if len(hits) > 5:
            lines.append(f'      ... {len(hits) - 5} more')
    pytest.fail('\n'.join(lines), pytrace=False)


EMOJI = (
    '[\U0001F000-\U0001FAFF☀-➿️‍⭐⭕⬛⬜⬅-⬇⤴⤵'
    '⌚⌛⏩-⏺Ⓜ▪▫▶◀◻-◾〰〽㊗㊙ℹ↔-↙↩↪]'
)
ALL_TEXT = lambda: _files('templates') + _files('js') + _files('css') + _files('prompts') + _files('py')  # noqa: E731
UI_TEXT = lambda: _files('templates') + _files('js') + _files('py')  # noqa: E731
PURPLE_WORDS = r'(purple|violet|indigo|fuchsia|pink|magenta|#7c3aed|#6d28d9|#8b5cf6|#a855f7|#9333ea|#667eea|#764ba2|#4f46e5|#6366f1|#4338ca|#ec4899|#db2777|#d946ef|#c026d3|#a78bfa)'


def test_no_emoji():
    _report('Emoji or pictographs (use the icon macro)', _scan_lines(ALL_TEXT(), EMOJI))


def test_no_em_dash():
    found = _merge(
        _scan_lines(ALL_TEXT(), '—|&mdash;|&#8212;|&#x2014;', re.I),
        _scan_lines(ALL_TEXT(), r'\s–\s|\s&ndash;\s|\s&#8211;\s', re.I),
    )
    _report('Em dash or spaced en dash (use a comma, colon, full stop or hyphen)', found)


def test_no_purple_gradients():
    paths = ALL_TEXT()
    found = _merge(
        _scan_lines(paths, r'gradient.*' + PURPLE_WORDS + '|' + PURPLE_WORDS + r'.*gradient', re.I),
        _scan_lines(paths, r'\b(from|via|to)-(purple|violet|indigo|fuchsia|pink)-\d', re.I),
        _scan_lines(paths, r'bg-clip-text|background-clip:\s*text', re.I),
        _scan_lines(paths, r'gradient-text|text-gradient', re.I),
    )
    _report('Purple/violet/indigo/pink gradient or gradient text', found)


def test_no_gradient_on_text_or_decor_classes():
    """Flat surfaces only: Tailwind gradient utilities are not part of the layout-only build."""
    found = _scan_lines(_files('templates') + _files('js'), r'\bbg-gradient-to-[a-z]{1,2}\b')
    _report('Tailwind gradient utility (bg-gradient-to-*)', found)


def test_no_pill_buttons_or_badges():
    html = _files('templates') + _files('js')
    found = _merge(
        _scan_tags(html, r'<button\b[^>]*>', r'rounded-full'),
        _scan_tags(html, r'<[a-z0-9]+\b[^>]*\bclass="[^"]*\bbtn\b[^"]*"[^>]*>', r'rounded-full'),
        _scan_tags(html, r'<[a-z0-9]+\b[^>]*\bclass="[^"]*\bbadge\b[^"]*"[^>]*>', r'rounded-full'),
        _scan_lines(_files('js'), r'(btn|badge).*rounded-full|rounded-full.*(btn|badge)'),
    )
    css_hits = defaultdict(list)
    block = re.compile(r'([^{}]+)\{([^{}]*)\}')
    for path in _files('css'):
        text = _read(path)
        for m in block.finditer(text):
            sel, body = m.group(1), m.group(2)
            if re.search(r'\.(btn|badge)\b', sel) and not re.search(r'::?(before|after)', sel) and re.search(r'border-radius:\s*(9999px|999px|9999rem|50rem|100%|50%)', body):
                css_hits[_rel(path)].append((text.count('\n', 0, m.start()) + 1, ' '.join(sel.split())[:80]))
    _report('Pill-shaped button or badge (radius is 6px, circles only for avatars and dots)', _merge(found, css_hits))


BANNED_PHRASES = [
    r'made with (love|ai|<i|❤)', r'powered by ai', r'trusted by', r'10,000', r'\b\d{1,3}(,\d{3})+\+?\s+(users|students|people|members|downloads)',
    r'happy (users|customers|students|clients)', r'testimonial', r'what (our )?(users|students) say', r'transform your', r'unlock your', r'revolutioni[sz]e',
    r'your ai-powered', r'clinically proven', r'hipaa[ -]compliant', r'end-to-end encrypt', r'military-grade', r'bank-grade',
    r'\boops\b',
]


def test_no_banned_copy():
    found = _scan_lines(UI_TEXT(), '|'.join(f'({p})' for p in BANNED_PHRASES), re.I)
    _report('Banned or unverifiable copy (fake claims, hype, "Made with", testimonials)', found)


def test_no_motion_gimmicks():
    rx = (r'cursor-follow|custom-cursor|cursor-glow|cursor-dot|cursor-trail|mouse-follow|cursor:\s*none|parallax|typewriter|typed\.js|'
          r'particles?(\.js|-js|-bg|-container)|tsparticles|data-aos|AOS\.init|scroll-reveal|reveal-on-scroll|animate-on-scroll|'
          r'autoplay.*carousel|carousel.*autoplay|bounce-arrow|animate-bounce')
    _report('Cursor effects, parallax, typewriter, particles or scroll reveal', _scan_lines(_files('templates') + _files('js') + _files('css'), rx, re.I))


def test_no_tailwind_cdn():
    rx = r'cdn\.tailwindcss\.com|tailwindcss@[0-9.]+/dist|tailwind(\.min)?\.css.*cdn|cdn.*tailwind(\.min)?\.css'
    _report('Tailwind CDN (link the built static/css/tailwind.css)', _scan_lines(_files('templates'), rx, re.I))


def test_no_jinja_in_static_js():
    _report('Jinja tag inside static JS (use data-* attributes or a JSON script block)', _scan_lines(_files('js'), r'\{\{|\{%'))


def test_no_tailwind_colour_utilities():
    """Colour comes from site.css tokens. Tailwind colour utilities break dark mode (see the legacy safety layer)."""
    rx = (r'(?<![\w-])(?:[a-z]+:)?(?:bg|text|border|from|to|via|ring|divide|placeholder|shadow)-'
          r'(?:gray|slate|zinc|neutral|stone|blue|indigo|purple|pink|red|green|yellow|orange|teal|cyan|sky|violet|fuchsia|rose|amber|emerald|lime)-\d{2,3}\b'
          r'|(?<![\w-])(?:bg-white|bg-black|text-white|text-black|border-white|bg-transparent)(?![\w-])')
    _report('Tailwind colour utility class (use semantic classes from DESIGN_SYSTEM.md)', _scan_lines(_files('templates') + _files('js'), rx))
