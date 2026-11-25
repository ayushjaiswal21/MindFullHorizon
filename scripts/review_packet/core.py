"""Shared global state and generic helpers for the review-packet exporter.

NOTES, CHECKS and _SRC are module-level globals, deliberately: every other module in this
package imports the functions below (note, check, src, ...) rather than re-declaring this
state, so a call from any module mutates the same lists/dict the final manifest reads.
"""
import ast
import csv
import hashlib
import importlib.util
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOTES = []
CHECKS = []   # (description, ok) drift checks: facts the narrative relies on, verified against the source

FINGERPRINT_FILES = [
    'ai/severity.py', 'ai/scoring.py', 'ai/service.py', 'ai/gemini_impl.py', 'ai_prompts/psychologist_system.txt',
    'utils/crisis.py', 'utils/helplines.py', 'utils/llm_guard.py', 'utils/jobs.py', 'utils/mailer.py',
    'routes/chat.py', 'routes/patient.py', 'routes/provider/__init__.py', 'routes/provider/analytics.py',
    'routes/provider/appointments.py', 'routes/provider/cli.py', 'routes/provider/dashboard.py',
    'routes/provider/documentation.py', 'routes/provider/helpers.py', 'routes/provider/wellness.py', 'app.py',
]

KEY_PATTERNS = [r'AIza[0-9A-Za-z_\-]{20,}', r'\bsk-[A-Za-z0-9_\-]{20,}', r'GOCSPX-[0-9A-Za-z_\-]{10,}',
                r'\bgh[pousr]_[A-Za-z0-9]{20,}', r'\bxox[abprs]-[A-Za-z0-9\-]{10,}', r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
                r'\bCNRY-[0-9a-f]{8,}', r'(?i)\b(?:api[_-]?key|secret|password|token)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}']
_KEY_RX = [re.compile(p) for p in KEY_PATTERNS]
CSV_CLINICIAN = ['clinician_verdict', 'severity_should_be', 'comment']


def note(msg):
    NOTES.append(msg)
    print('NOTE: ' + msg)


def check(desc, ok):
    CHECKS.append((desc, bool(ok)))
    if not ok:
        print('DRIFT CHECK FAILED: ' + desc)
    return ok


# ---------------------------------------------------------------- generic helpers
def path_of(rel):
    return os.path.join(ROOT, *rel.split('/'))


_SRC = {}


def src(rel):
    """Text of a project file, '' (with one NOTE) when missing."""
    if rel not in _SRC:
        try:
            with open(path_of(rel), encoding='utf-8') as f:
                _SRC[rel] = f.read()
        except OSError:
            _SRC[rel] = ''
            note(f'file not found, related output is incomplete: {rel}')
    return _SRC[rel]


def tree_of(rel):
    try:
        return ast.parse(src(rel))
    except SyntaxError:
        note(f'could not parse {rel}')
        return ast.parse('')


def load(name, rel):
    """Load a pure module by file path. None (with a NOTE) if absent or broken."""
    p = path_of(rel)
    if not os.path.isfile(p):
        note(f'module missing, skipped: {rel}')
        return None
    try:
        spec = importlib.util.spec_from_file_location('_review_' + name, p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:  # noqa: BLE001 - any failure must degrade, never crash
        note(f'module could not be loaded, skipped: {rel} ({type(exc).__name__})')
        return None


def redact(text):
    s = str(text)
    canary = os.environ.get('AI_CANARY')
    if canary and len(canary) >= 6:
        s = s.replace(canary, '[CANARY REDACTED]')
    for rx in _KEY_RX:
        s = rx.sub('[REDACTED]', s)
    return s


def write_text(out, name, text):
    with open(os.path.join(out, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(redact(text).rstrip('\n') + '\n')


def write_csv(out, name, header, rows):
    # utf-8 with BOM so that Excel shows Devanagari correctly
    with open(os.path.join(out, name), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(header)
        for r in rows:
            w.writerow([redact(c) for c in r])


def script(text):
    if re.search('[ऀ-ॿ]', text):
        return 'Devanagari'
    if re.search(r'\b(?:nahi|nhi|nahin|mujhe|mera|meri|marna|jeena|jeene|khud|khatam|zindagi|jindagi|thak|dost|yaar|'
                 r'raha|rahi|chahta|chahti|chahat|hu|hoon|hai|aur|kya|sharam|jaun|jaunga|jaana|jana|jaye|hamesha|'
                 r'dikhai|apni|apna|jaan|suicide ki|khudkushi|khushi)\b', text.lower()):
        return 'Hinglish'
    return 'English'


def git_info():
    def run(*args):
        try:
            return subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:  # noqa: BLE001
            return ''
    head = run('rev-parse', 'HEAD')
    if not head:
        return 'unavailable (not a git repository or git not installed)', 'unknown'
    dirty = [ln for ln in run('status', '--porcelain', '--', 'ai', 'utils', 'routes', 'ai_prompts', 'app.py',
                              'models.py').splitlines() if ln.strip()]
    return head, (f'{len(dirty)} safety-relevant file(s) have uncommitted changes: the packet reflects the working '
                  'tree, not the commit' if dirty else 'clean (safety-relevant paths match the commit)')


def fingerprints():
    out = []
    for rel in FINGERPRINT_FILES:
        p = path_of(rel)
        if os.path.isfile(p):
            with open(p, 'rb') as f:
                data = f.read().replace(b'\r\n', b'\n')
            out.append((rel, hashlib.sha256(data).hexdigest()[:16]))
        else:
            out.append((rel, 'missing'))
    return out


def md_header(title, stamp, commit, dirty):
    return (f'# {title}\n\nGenerated by `scripts/export_review_packet.py` from the live code. Do not edit by hand: '
            f're-run the script.\n\n- Generated at (UTC): {stamp}\n- Git commit: `{commit}`\n- Working tree: {dirty}\n'
            '- Status: **not clinically validated, not legally reviewed.** This file states what the code does today.\n')


def excerpt(rel, pattern, flags=0, context=0, limit=3):
    """Verbatim source lines matching `pattern`, as 'rel:line: text'. Empty list when not found."""
    lines = src(rel).splitlines()
    rx = re.compile(pattern, flags)
    out = []
    for i, ln in enumerate(lines):
        if rx.search(ln):
            for j in range(max(0, i - context), min(len(lines), i + context + 1)):
                out.append(f'{rel}:{j + 1}: {lines[j].rstrip()}')
            if len(out) >= limit * (2 * context + 1):
                break
    return out


def first_match(rel, pattern, group=1, flags=0, default=None):
    m = re.search(pattern, src(rel), flags)
    return m.group(group) if m else default
