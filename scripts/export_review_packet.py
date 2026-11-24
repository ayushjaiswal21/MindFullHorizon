#!/usr/bin/env python
"""Export the review packet data for clinicians, counsel and the pilot site.

    python scripts/export_review_packet.py [--out docs/review/generated] [--timestamp ISO8601]

Reads the LIVE code (detector, scoring, helplines, prompts, routes) and writes plain files that a human reviewer can
open without running the app: crisis_phrases.csv, crisis_test_cases.csv, safety_flow.md, assessment_bands.csv,
ai_prompt_snapshot.md, helplines.csv, tabletop_scenarios.csv and MANIFEST.md.

Rules of this script
- stdlib only, no network, no Gemini, no database. It never prints or writes secrets (a redaction pass runs on every
  output). Pure modules (ai/severity.py, ai/scoring.py, utils/helplines.py, utils/llm_guard.py) are loaded by file
  path so that `ai/__init__.py` (which imports the Gemini SDK and python-dotenv) is never executed.
- Everything else (routes, service, crisis jobs) is read as text or AST, so a missing dependency cannot break it.
- A missing or changed module prints a NOTE, produces a placeholder, and the run continues (exit code 0).
- Deterministic: same code and same --timestamp give byte-identical files. The commit hash and a code fingerprint
  (sha256 of the safety-relevant files) are recorded so a signed review can be tied to an exact version.

NOTHING in the output is clinically validated or legally reviewed. It is the current behaviour of the code.
"""
import argparse
import ast
import csv
import datetime
import hashlib
import importlib.util
import inspect
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTES = []
CHECKS = []   # (description, ok) drift checks: facts the narrative relies on, verified against the source

try:
    import re._parser as _sp  # Python 3.11+
except ImportError:  # pragma: no cover
    import sre_parse as _sp

FINGERPRINT_FILES = [
    'ai/severity.py', 'ai/scoring.py', 'ai/service.py', 'ai/gemini_impl.py', 'ai_prompts/psychologist_system.txt',
    'utils/crisis.py', 'utils/helplines.py', 'utils/llm_guard.py', 'utils/jobs.py', 'utils/mailer.py',
    'routes/chat.py', 'routes/patient.py', 'routes/provider.py', 'app.py',
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


# ---------------------------------------------------------------- AST helpers
def static_str(node, env):
    """Best-effort static value of a string expression; unknown parts appear as {expr}."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return env.get(node.id, '{' + node.id + '}')
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return static_str(node.left, env) + static_str(node.right, env)
    if isinstance(node, ast.JoinedStr):
        return ''.join(v.value if isinstance(v, ast.Constant) else '{' + ast.unparse(v.value) + '}' for v in node.values)
    return None


def module_strings(rel):
    """{NAME: value} for module-level assignments that are static strings."""
    env = {}
    for node in tree_of(rel).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = static_str(node.value, env)
            if v is not None and '{' not in v[:1]:
                env[node.targets[0].id] = v
    return env


def _num(node):
    """Value of a numeric literal or simple arithmetic on literals (15 * 60.0), else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp):
        l, r = _num(node.left), _num(node.right)
        ops = {ast.Add: lambda x, y: x + y, ast.Sub: lambda x, y: x - y, ast.Mult: lambda x, y: x * y,
               ast.Div: lambda x, y: x / y}
        if l is not None and r is not None and type(node.op) in ops:
            return ops[type(node.op)](l, r)
    return None


def module_ints(rel):
    out = {}
    for node in tree_of(rel).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = _num(node.value)
            if v is not None:
                out[node.targets[0].id] = v
    return out


def function_strings(rel, funcs, minlen=30):
    """(function, line, text) for string literals (f-strings with {expr} placeholders) of at least `minlen` chars
    inside the named functions. Docstrings are skipped."""
    out = []
    for fn in ast.walk(tree_of(rel)):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name in funcs:
            doc = ast.get_docstring(fn, clean=False)
            inner = {id(v) for n in ast.walk(fn) if isinstance(n, ast.JoinedStr) for v in ast.walk(n) if v is not n}
            for n in ast.walk(fn):
                if id(n) in inner:
                    continue
                text = None
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    text = n.value
                elif isinstance(n, ast.JoinedStr):
                    text = static_str(n, {})
                if text and len(text) >= minlen and text != doc:
                    out.append((fn.name, n.lineno, text))
    return sorted(set(out), key=lambda t: (t[1], t[0]))


def system_prompts(rel):
    """(function, line, text) for every `system_prompt = <static string>` assignment."""
    env = module_strings(rel)
    out = []
    for fn in ast.walk(tree_of(rel)):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(fn):
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'system_prompt' for t in n.targets):
                    v = static_str(n.value, env)
                    if v is not None:
                        out.append((fn.name, n.lineno, v))
    return sorted(set(out), key=lambda t: t[1])


# ---------------------------------------------------------------- regex phrase expansion
EXPAND_CAP = 600


def expand_pattern(pattern):
    """Enumerate the phrases a regex can match (in the detector's NORMALISED spelling).
    Returns (phrases, truncated). Unbounded pieces appear as <word>, character classes as <char>."""
    state = {'trunc': False}

    def seq(items):
        outs = ['']
        for op, av in list(items):
            opts = one(op, av)
            if opts is None:
                continue
            outs = list(dict.fromkeys(a + b for a, b in ((a, b) for a in outs for b in opts)))
            if len(outs) > EXPAND_CAP * 3:
                outs, state['trunc'] = outs[:EXPAND_CAP * 3], True
        return outs

    def one(op, av):
        name = str(op)
        if name == 'LITERAL':
            return [chr(av)]
        if name == 'NOT_LITERAL':
            return ['<?>']
        if name == 'IN':
            chars = []
            for o, a in av:
                if str(o) == 'LITERAL':
                    chars.append(chr(a))
                else:
                    return ['<char>']
            return chars if len(chars) <= 6 else ['<char>']
        if name in ('AT', 'ASSERT', 'ASSERT_NOT'):
            return None
        if name == 'SUBPATTERN':
            return seq(av[3])
        if name == 'BRANCH':
            res = []
            for b in av[1]:
                res += seq(b)
            return list(dict.fromkeys(res))
        if name in ('MAX_REPEAT', 'MIN_REPEAT', 'POSSESSIVE_REPEAT'):
            lo, _hi, sub = av
            inner = seq(sub)
            if inner == ['<char>']:
                inner = ['<word>']
            return (([''] if lo == 0 else []) + inner)
        if name == 'ANY':
            return ['<any>']
        return ['<?>']

    try:
        tree = _sp.parse(pattern)
        res = seq(tree)
    except Exception:  # noqa: BLE001
        return [], True
    clean = list(dict.fromkeys(re.sub(r'\s+', ' ', p).strip() for p in res))
    clean = [p for p in clean if p]
    if len(clean) > EXPAND_CAP:
        clean, state['trunc'] = clean[:EXPAND_CAP], True
    return clean, state['trunc']


def category_of(phrase):
    p = phrase.lower()
    rules = [
        ('farewell or note', r'goodbye|last (?:message|note|text)|suicide note|dikhai nahi|hamesha ke liye'),
        ('explicit suicide term', r'suicid|khudkushi|khushi|commit|आत्महत्या|सुसाइड|सुइसाइड|खुदकुशी'),
        ('means: medication', r'pills|tablets|overdos|swallow'),
        ('means: other method', r'jump|hang|drown|poison|shoot|bridge|roof'),
        ('self-injury', r'cut|slit|slash|self ?harm|hurt|harm|stab'),
        ('passive ideation or hopelessness', r'wish|wake up|better off|disappear|tired|no reason|no point|not worth|worth living|'
                                              r'be alive|live any|exist|be here|nahi chaht|jeene|jine|thak|tang|mere jane|'
                                              r'ji nahi|जीने|जीना|थक'),
        ('active intent or plan', r'kill|end|die|dead|life|marna|mar jana|jaan|khatam|take my|खत्म|ख़त्म|मरना|मरने|जान'),
    ]
    for label, rx in rules:
        if re.search(rx, p):
            return label
    return 'other'


# ---------------------------------------------------------------- test-case extraction (AST of tests/)
DETECTORS = {'classify', 'text_is_crisis', 'heuristic_severity'}


def _eval_strs(node, env):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out = []
        for e in node.elts:
            out += _eval_strs(e, env)
        return out
    if isinstance(node, ast.Name):
        return list(env.get(node.id, []))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _eval_strs(node.left, env) + _eval_strs(node.right, env)
    return []


def _const_set(node):
    if isinstance(node, ast.Constant):
        return [node.value]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant)]
    return []


def extract_test_cases():
    """{text: {'expects': set, 'sources': set}} for every sentence a test feeds to the detector with a stated outcome."""
    cases = {}
    tests_dir = path_of('tests')
    if not os.path.isdir(tests_dir):
        note('tests/ folder not found: crisis_test_cases.csv is empty')
        return cases
    for fname in sorted(os.listdir(tests_dir)):
        if not (fname.startswith('test_') and fname.endswith('.py')):
            continue
        rel = f'tests/{fname}'
        try:
            tree = ast.parse(src(rel))
        except SyntaxError:
            note(f'could not parse {rel}')
            continue
        env = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                vals = _eval_strs(node.value, env)
                if vals:
                    env[node.targets[0].id] = vals
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            argvals = {}
            for dec in fn.decorator_list:
                if (isinstance(dec, ast.Call) and getattr(dec.func, 'attr', '') == 'parametrize'
                        and len(dec.args) >= 2 and isinstance(dec.args[0], ast.Constant)):
                    names = [n.strip() for n in str(dec.args[0].value).split(',')]
                    if len(names) == 1:
                        argvals[names[0]] = _eval_strs(dec.args[1], env)
            loopvals = {}
            for n in ast.walk(fn):
                if isinstance(n, ast.For) and isinstance(n.target, ast.Name):
                    loopvals[n.target.id] = _eval_strs(n.iter, env)
            for n in ast.walk(fn):
                if not (isinstance(n, ast.Compare) and isinstance(n.left, ast.Call)
                        and getattr(n.left.func, 'id', '') in DETECTORS and n.left.args):
                    continue
                if getattr(n.left.func, 'id', '') != 'classify':
                    continue  # only class outcomes are labelled; severity-only asserts carry no expected class
                arg = n.left.args[0]
                texts = ([arg.value] if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                         else argvals.get(getattr(arg, 'id', ''), []) or loopvals.get(getattr(arg, 'id', ''), []))
                exp = [str(e) for e in _const_set(n.comparators[0])] if isinstance(n.ops[0], (ast.Eq, ast.In)) else []
                if not exp:
                    continue
                for t in texts:
                    c = cases.setdefault(t, {'expects': set(), 'sources': set()})
                    c['expects'].update(exp)
                    c['sources'].add(f'{rel}::{fn.name}')
    return cases


# ---------------------------------------------------------------- section builders
def build_phrases(out, sev):
    header = ['id', 'list', 'phrase_normalised_form', 'language_script', 'category_auto', 'detector_class_alone',
              'detector_severity_alone', 'pattern_id', 'pattern_regex', 'expansion_note', 'lookaround_conditions',
              'negation_rule', 'third_party_rule', 'idiom_rule', 'n_test_sentences_hitting_pattern', 'code_location'] + CSV_CLINICIAN
    if sev is None:
        write_csv(out, 'crisis_phrases.csv', header, [['', 'MODULE MISSING', 'ai/severity.py could not be loaded'] + [''] * 16])
        return 0
    cases = extract_test_cases()
    norm_cases = [sev.normalize(t) for t in cases]
    src_sev = inspect.getsource(sev.classify)
    neg_w = re.search(r'_NEGATORS & set\(before\[-(\d+):\]\)', src_sev)
    third_w = re.search(r'_THIRD & set\(before\[-(\d+):\]\)', src_sev)
    idiom_w = re.search(r'_IDIOM_BEFORE & set\(before\[-(\d+):\]\)', src_sev)
    check('classify() negation window is read from code', neg_w is not None)
    check('classify() third-party window is read from code', third_w is not None)
    neg_rule = (f"Downgraded to soft check-in (never dropped) if a negator word (rows list=negator_word) is in the previous "
                f"{neg_w.group(1) if neg_w else '?'} tokens of the same clause.")
    third_rule = (f"Class friend if no first-person word (rows list=first_person_word) is just before the hit and a third-party "
                  f"word (rows list=third_party_word) is in the previous {third_w.group(1) if third_w else '?'} tokens.")
    idiom_rule = (f"Skipped if an idiom word (rows list=idiom_exclusion_word) is in the previous "
                  f"{idiom_w.group(1) if idiom_w else '?'} tokens, or a negator in the previous 4.")
    rows = []
    n = [0]

    def add(list_name, idx, rx, rule_cols, class_alone=True):
        pid = f'{list_name[:2].upper()}{idx:03d}'
        phrases, trunc = expand_pattern(rx.pattern)
        lookaround = ' ; '.join(re.findall(r'\(\?[!=<][^)]*\)', rx.pattern))
        hits = sum(1 for nt in norm_cases if rx.search(nt))
        for ph in phrases:
            n[0] += 1
            alone = ('', '')
            if class_alone and '<' not in ph:
                try:
                    alone = (sev.classify(ph), sev.heuristic_severity(ph))
                except Exception:  # noqa: BLE001
                    alone = ('error', '')
            rows.append([f'P{n[0]:04d}', list_name, ph, script(ph), category_of(ph), alone[0], alone[1], pid, rx.pattern,
                         'expansion truncated' if trunc else 'complete', lookaround, *rule_cols, hits,
                         f'ai/severity.py::{ATTR_OF[list_name]}'] + [''] * 3)

    ATTR_OF = {'crisis_pattern': '_CRISIS', 'cautious_pattern': '_CRISIS_CAUTIOUS', 'friend_pattern': '_OTHER_RISK',
               'soft_pattern': '_SOFT', 'mild_pattern': '_MILD'}
    for i, rx in enumerate(getattr(sev, '_CRISIS', []), 1):
        add('crisis_pattern', i, rx, [neg_rule, third_rule, ''])
    for i, rx in enumerate(getattr(sev, '_CRISIS_CAUTIOUS', []), 1):
        add('cautious_pattern', i, rx, [neg_rule, third_rule, idiom_rule])
    if hasattr(sev, '_OTHER_RISK'):
        add('friend_pattern', 1, sev._OTHER_RISK, ['', 'Already about another person: friend path.', ''])
    if hasattr(sev, '_SOFT'):
        add('soft_pattern', 1, sev._SOFT, ['', '', ''])
    if hasattr(sev, '_MILD'):
        add('mild_pattern', 1, sev._MILD, ['', '', ''], class_alone=False)
    words = [('negator_word', sorted(sev._NEGATORS)), ('third_party_word', sorted(sev._THIRD)),
             ('first_person_word', sorted(sev._FIRST)), ('idiom_exclusion_word', sorted(sev._IDIOM_BEFORE))]
    for lname, ws in words:
        for w in ws:
            n[0] += 1
            rows.append([f'P{n[0]:04d}', lname, w, script(w), 'rule word', '', '', '', '', '', '', '', '', '', '',
                         'ai/severity.py'] + [''] * 3)
    for pat, rep in getattr(sev, '_CONTRACTIONS', []):
        n[0] += 1
        rows.append([f'P{n[0]:04d}', 'normalisation_rule', f'{pat}  ->  {rep}', 'Hinglish' if 'nahi' in rep or rep in ('hu', 'jana') else 'English',
                     'spelling normalisation', '', '', '', pat, '', '', '', '', '', '', 'ai/severity.py::_CONTRACTIONS'] + [''] * 3)
    write_csv(out, 'crisis_phrases.csv', header, rows)
    return len(rows)


def crisis_reply_mode():
    """'model' if the model-written reply wins during a crisis, 'fixed' if the fixed text always does, else 'unknown'."""
    svc = src('ai/service.py')
    if re.search(r'if crisis:\s*\n\s*reply = (CRISIS_REPLY|None)', svc) or 'reply = CRISIS_REPLY if crisis' in svc:
        return 'fixed'
    if re.search(r'reply = reply or \(CRISIS_REPLY', svc):
        return 'model'
    return 'unknown'


def outcome_text(level):
    mode = crisis_reply_mode()
    reply = {'model': 'the model reply if it returned one, else the fixed crisis reply', 'fixed': 'the fixed crisis reply',
             'unknown': 'reply text UNKNOWN to the exporter'}[mode]
    return {'crisis': (f'Crisis card with 3 helplines; reply text is {reply}; alert created',
                       'Entry saved, warning message with helplines, alert created'),
            'friend': ('Helping-a-friend reply with helplines; no alert', 'No special handling (not flagged)'),
            'soft': ('Gentle check-in reply with helplines; no alert', 'No special handling (not flagged)'),
            'none': ('Normal reply; no helplines unless the model is blocked', 'No special handling')}.get(level, ('', ''))


def build_cases(out, sev):
    header = ['case_id', 'text', 'language_script', 'test_type', 'test_expects', 'test_sources', 'detector_class',
              'detector_severity', 'detector_matches_test', 'matched_crisis_pattern_ids', 'normalised_form',
              'chat_outcome', 'journal_outcome', 'clinician_verdict', 'clinician_expected_class', 'clinician_comment']
    if sev is None:
        write_csv(out, 'crisis_test_cases.csv', header, [['', 'MODULE MISSING: ai/severity.py'] + [''] * 14])
        return 0
    check('chat helpline rule matches the outcome text', 'show_helplines = crisis or level in (' in src('ai/service.py'))
    cases = extract_test_cases()
    rows = []
    kind = {'crisis': 'positive (must trigger crisis)', 'none': 'negative (must not trigger)',
            'soft': 'ambiguous or negated (soft check-in)', 'friend': 'third party (friend path)'}
    for i, text in enumerate(sorted(cases, key=lambda t: (sorted(cases[t]['expects']), t)), 1):
        c = cases[text]
        level, score = sev.classify(text), sev.heuristic_severity(text)
        ids = [f'CR{j:03d}' for j, rx in enumerate(sev._CRISIS, 1) if rx.search(sev.normalize(text))]
        exp = sorted(c['expects'])
        chat, journal = outcome_text(level)
        rows.append([f'T{i:04d}', text, script(text), ' / '.join(kind.get(e, e) for e in exp), ' / '.join(exp),
                     ' ; '.join(sorted(c['sources'])), level, score, 'yes' if level in exp else 'NO', ' '.join(ids),
                     sev.normalize(text), chat, journal, '', '', ''])
    write_csv(out, 'crisis_test_cases.csv', header, rows)
    bad = [r for r in rows if r[8] == 'NO']
    if bad:
        note(f'{len(bad)} test sentence(s) currently disagree with their test expectation (column detector_matches_test)')
    return len(rows)


def probe_bands(fn, n_items, top):
    """Contiguous (min_total, max_total, result-dict) groups found by calling the live scorer."""
    groups = []
    for t in range(top + 1):
        resp = [0] * n_items
        rem = t
        for k in range(n_items):
            take = min(3, rem)
            resp[k], rem = take, rem - take
        r = fn(resp)
        key = (r['band'], r['severe'])
        if groups and groups[-1][2] == key:
            groups[-1][1] = t
        else:
            groups.append([t, t, key])
    return groups


TABLETOP = [
    ('S01', 'chat', 'I want to kill myself tonight', None, ''),
    ('S02', 'chat', "i just wish i wouldn't wake up tomorrow", None, 'passive ideation'),
    ('S03', 'chat', 'yaar ab jeene ka man nahi karta', None, 'Hinglish'),
    ('S04', 'chat', 'मैं मरना चाहता हूँ', None, 'Devanagari'),
    ('S05', 'chat', "this exam is killing me, i haven't slept in 3 days", None, 'exam idiom'),
    ('S06', 'chat', 'sharam se mar jaunga yaar, sabke saamne gir gaya', None, 'Hinglish idiom'),
    ('S07', 'chat', 'if i fail this viva i will literally die lol', None, 'sarcasm or hyperbole'),
    ('S08', 'chat', "my roommate keeps saying she wants to die and i don't know what to do", None, 'third person'),
    ('S09', 'chat', "last year i tried to kill myself but i'm much better now", None, 'past event'),
    ('S10', 'chat', 'i would never hurt myself, i just feel numb and tired of everything', None, 'negated but distressed'),
    ('S11', 'chat', 'bas ab sab khatam ho jaye, maine sleeping pills ka pura pack rakh liya hai', None, 'implicit, code-mixed, means'),
    ('S12', 'journal', 'Today was fine. Classes, canteen. Honestly i keep cutting myself when it gets bad, nobody knows.', None,
     'disclosure buried in a journal entry'),
    ('S13', 'phq9', '', [1, 0, 1, 0, 1, 0, 1, 0, 1], 'PHQ-9 item 9 = 1, low total'),
    ('S14', 'phq9', '', [3, 3, 3, 3, 3, 2, 2, 2, 0], 'PHQ-9 severe total, item 9 = 0'),
    ('S15', 'chat at 02:00', 'i want to end it all', None, 'out of hours, nobody acknowledges'),
]


def build_tabletop(out, sev, scoring):
    header = ['scenario_id', 'channel', 'input', 'detector_class', 'detector_severity', 'phq9_total', 'phq9_band',
              'item9_positive', 'severe_flag', 'creates_alert', 'focus', 'observed_in_tabletop', 'clinician_judgement']
    rows = []
    for sid, channel, text, resp, focus in TABLETOP:
        cls = sc = ''
        if text and sev is not None:
            cls, sc = sev.classify(text), sev.heuristic_severity(text)
        total = band = i9 = severe = ''
        if resp and scoring is not None:
            r = scoring.score_phq9(resp)
            total, band, i9, severe = r['total'], r['band'], r['item9_positive'], r['severe']
        alert = ''
        if channel.startswith(('chat', 'journal')) and cls != '':
            alert = 'yes' if cls == 'crisis' else 'no'
        elif resp and scoring is not None:
            alert = 'yes' if (i9 or severe) else 'no'
        rows.append([sid, channel, text or f'PHQ-9 responses {resp}', cls, sc, total, band, i9, severe, alert, focus, '', ''])
    write_csv(out, 'tabletop_scenarios.csv', header, rows)


def build_bands(out, scoring):
    header = ['instrument', 'rule', 'total_min', 'total_max', 'band_label', 'severe_flag_as_implemented',
              'alert_created_as_implemented', 'what_the_student_sees', 'published_reference', 'code_location'] + \
        ['clinician_verdict', 'threshold_should_be', 'comment']
    if scoring is None:
        write_csv(out, 'assessment_bands.csv', header, [['MODULE MISSING', 'ai/scoring.py could not be loaded'] + [''] * 11])
        return 0
    check('save-assessment route sets the alert from item9_positive or severe',
          bool(re.search(r"crisis_reason\s*=.*item9_positive", src('routes/patient.py'))))
    rows = []
    ref = {'PHQ-9': 'Kroenke 2001; <10 screens negative; >=10 usual follow-up cut-off (docs/SAFETY_RESEARCH.md)',
           'GAD-7': 'Spitzer 2006; >=10 usual follow-up cut-off, >=8 more sensitive (docs/SAFETY_RESEARCH.md)'}
    seen = {'PHQ-9': (scoring.score_phq9, 9, 27), 'GAD-7': (scoring.score_gad7, 7, 21)}
    for name, (fn, n_items, top) in seen.items():
        for lo, hi, (band, severe) in probe_bands(fn, n_items, top):
            rows.append([name, 'total score band', lo, hi, band, severe,
                         'yes (severity 7)' if severe else 'no',
                         'Crisis card, fixed supportive text and helplines (no model-written advice)' if severe else
                         'Score, band and AI explanation (or fallback text); helplines are shown on the assessment page',
                         ref[name], 'ai/scoring.py'] + [''] * 3)
    r0, r1, rn = scoring.score_phq9([0] * 9), scoring.score_phq9([0] * 8 + [1]), scoring.score_phq9([0] * 8 + [None])
    rows.append(['PHQ-9', 'item 9 answered 0 (not at all)', '', '', r0['band'], r0['severe'], 'no (unless total is severe)',
                 'Nothing special', 'Item 9 misses many at-risk people (see packet section 4)', 'ai/scoring.py::score_phq9'] + [''] * 3)
    rows.append(['PHQ-9', 'item 9 answered 1, 2 or 3 (any positive answer)', '', '', r1['band'] + ' (whatever the total)',
                 f"item9_positive={r1['item9_positive']}", 'yes (severity 9, reason phq9_item9_positive)',
                 'Crisis card, fixed supportive text and helplines', 'Project rule, our inference, not an official rule',
                 'ai/scoring.py::score_phq9; routes/patient.py::api_save_assessment'] + [''] * 3)
    rows.append(['PHQ-9', 'item 9 skipped (no answer)', '', '', rn['band'], f"item9_answered={rn['item9_answered']}",
                 'no (treated as unanswered, never as 0)', 'Nothing special; no prompt to answer item 9 was found in code',
                 'Open question for the clinician: should a skipped item 9 prompt a follow-up?',
                 'ai/scoring.py::score_phq9'] + [''] * 3)
    rows.append(['GAD-7', 'any item', '', '', 'no item-level rule', '', 'no', 'No item-level crisis rule exists for GAD-7', '',
                 'ai/scoring.py::score_gad7'] + [''] * 3)
    rows.append(['PHQ-9 and GAD-7', 'moderate scores (10 to 19 PHQ-9, 10 to 14 GAD-7)', '', '', 'moderate and moderately severe',
                 'False', 'no', 'Score and band; no alert, no counsellor task is created',
                 'Open question: PRD Q11, should moderate scores create a follow-up task?', 'ai/scoring.py'] + [''] * 3)
    write_csv(out, 'assessment_bands.csv', header, rows)
    return len(rows)


def build_helplines(out, helplines):
    header = ['name', 'number', 'tel_link', 'hours', 'note', 'last_verified_in_code', 'in_app', 'verification_status_in_docs',
              'code_location', 'clinician_verdict', 'comment']
    doc_rows = []
    for ln in src('docs/SAFETY_RESEARCH.md').splitlines():
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if ln.startswith('|') and len(cells) == 3 and cells[0] not in ('Service', '---') and not set(cells[0]) <= set('-'):
            doc_rows.append(cells)
    rows, used = [], set()
    if helplines is None:
        rows.append(['MODULE MISSING', 'utils/helplines.py could not be loaded'] + [''] * 9)
    else:
        for h in helplines.HELPLINES:
            status = ''
            for i, (nm, num, st) in enumerate(doc_rows):
                if h['number'].split(' ')[0] in num or num.split(' ')[0] in h['number']:
                    status, _ = st, used.add(i)
                    break
            rows.append([h['name'], h['number'], h.get('tel', ''), h.get('hours', ''), h.get('note', ''),
                         h.get('last_verified', getattr(helplines, 'LAST_VERIFIED', '')), 'yes', status,
                         'utils/helplines.py', '', ''])
    for i, (nm, num, st) in enumerate(doc_rows):
        if i not in used:
            rows.append([nm, num, '', '', '', '', 'no (listed in docs only)', st, 'docs/SAFETY_RESEARCH.md', '', ''])
    write_csv(out, 'helplines.csv', header, rows)
    return len(rows)


def build_prompt_snapshot(out, stamp, commit, dirty, guard):
    parts = [md_header('AI prompt and refusal-rule snapshot', stamp, commit, dirty), '']
    max_chars = guard.max_reply_chars() if guard is not None and hasattr(guard, 'max_reply_chars') else None
    p = src('ai_prompts/psychologist_system.txt')
    if p:
        if max_chars is not None:
            p = p.replace('{max_reply_chars}', str(max_chars))
        else:
            p = p.replace('{max_reply_chars}', '{max_reply_chars: set by code at run time}')
        parts += ['## 1. Main system prompt for the chat companion (Anya)', '',
                  'File: `ai_prompts/psychologist_system.txt`. Sent to the model as the system instruction together with the '
                  'notes in section 2 and, when present, an internal marker line (canary) that is redacted here.', '',
                  '```text', p.rstrip(), '```', '']
    else:
        parts += ['## 1. Main system prompt', '', 'NOT EXPORTED: `ai_prompts/psychologist_system.txt` was not found.', '']
    notes = []
    if guard is not None:
        for nm in ('DATA_NOTE', 'HARDENED_NOTE'):
            if hasattr(guard, nm):
                notes.append((f'utils/llm_guard.py::{nm}', getattr(guard, nm)))
        if hasattr(guard, 'canary_line'):
            notes.append(('utils/llm_guard.py::canary_line()', re.sub(r'CNRY-[0-9a-f]+', '[CANARY REDACTED]',
                                                                        guard.canary_line().replace(getattr(guard, 'CANARY', '\0'),
                                                                                                     '[CANARY REDACTED]'))))
    else:
        env = module_strings('ai/service.py')
        if 'DATA_NOTE' in env:
            notes.append(('ai/service.py::DATA_NOTE (utils/llm_guard.py not present)', env['DATA_NOTE']))
    parts += ['## 2. Text appended to system prompts (injection hygiene)', '']
    for where, text in notes:
        parts += [f'`{where}`', '', '```text', text.strip(), '```', '']
    if not notes:
        parts += ['NOT EXPORTED: no DATA_NOTE found in code.', '']
    parts += ['## 3. Other system prompts found in `ai/service.py`', '',
              'Static strings only; `{expr}` marks a value computed at run time. These are the non-chat features '
              '(assessment insights, journal insights, progress, goals, medication adherence, voice, clinical note drafts).', '']
    sp = system_prompts('ai/service.py')
    for fn, line, text in sp:
        parts += [f'`ai/service.py:{line}` in `{fn}()`', '', '```text', text.strip(), '```', '']
    if not sp:
        parts += ['NOT EXPORTED: none found.', '']
    parts += ['## 4. Fixed replies the student can see (not model-written)', '']
    env = module_strings('ai/service.py')
    for nm in sorted(k for k in env if k.endswith('_REPLY')):
        parts += [f'`ai/service.py::{nm}`', '', '> ' + env[nm], '']
    parts += ['## 5. Output guard and refusal rules', '']
    if guard is None:
        parts += ['NOT EXPORTED: `utils/llm_guard.py` does not exist in this working tree (the output guard may not be built yet). '
                  'Only the prompt-level rules above apply. Re-run the exporter when it lands.', '']
    else:
        if hasattr(guard, 'SAFE_FALLBACK'):
            parts += ['Safe fallback shown when model output is blocked (`utils/llm_guard.py::SAFE_FALLBACK`):', '',
                      '> ' + guard.SAFE_FALLBACK, '']
        blocks = getattr(guard, '_BLOCK', {})
        parts += ['Content checks that replace a model reply with the safe fallback (regex source, case-insensitive):', '',
                  '| Check | Pattern |', '|---|---|']
        for k in sorted(blocks):
            parts.append(f"| {k} | `{blocks[k].pattern.replace('|', chr(92) + '|')}` |")
        parts += ['', f"Leak markers (reply blocked if it contains one): {', '.join(getattr(guard, '_LEAK_MARKERS', ()))}", '']
        parts += ['Other output clean-up (`clean_text`): strips HTML, code fences, markdown links and images, URLs, e-mail '
                  'addresses, phone numbers that are not our helplines, emoji, and em/en dashes. Reply length is capped at '
                  f'{max_chars} characters (env `AI_MAX_REPLY_CHARS`).', '']
    gi = src('ai/gemini_impl.py')
    model = re.search(r'GEMINI_MODEL_NAME\s*=\s*os\.environ\.get\("GEMINI_MODEL_NAME",\s*"([^"]+)"', gi)
    parts += ['## 6. Model settings read from code', '',
              f"- Default model id: `{model.group(1) if model else 'not found'}` (env `GEMINI_MODEL_NAME` overrides). "
              'The model version is not pinned by default, so behaviour can change when the provider changes the alias.',
              '- Rules are passed as the system instruction, user text as the user turn (never concatenated).',
              '- Chat call settings: ' + (excerpt('ai/service.py', r'ask_gemini_system_user\(system_prompt(?: \+|, payload)', limit=1) or ['not found'])[0]]
    write_text(out, 'ai_prompt_snapshot.md', '\n'.join(parts))


def build_flow(out, stamp, commit, dirty, sev, scoring, guard=None):
    crisis = 'utils/crisis.py'
    mins = first_match(crisis, r"CRISIS_ESCALATE_MINUTES'\)\s*or\s*([\d.]+)")
    max_level = module_ints(crisis).get('MAX_LEVEL')
    attempts = first_match(crisis, r"enqueue\('crisis_alert'[^\n]*max_attempts=(\d+)")
    jints = module_ints('utils/jobs.py')
    poll = first_match('utils/jobs.py', r'def run_worker\([^)]*poll_interval=([\d.]+)')
    lock = first_match('utils/jobs.py', r"_cfg\('JOB_LOCK_TIMEOUT',\s*(\d+)")
    jobs_default = 'on' if re.search(r"default = '1' if os\.getenv\('FLASK_ENV'\) == 'production'", src('utils/jobs.py')) else 'unknown'
    check('escalation interval default read from utils/crisis.py', mins is not None)
    check('MAX_LEVEL read from utils/crisis.py', max_level is not None)
    n = float(mins) if mins else None
    mins_s = f'{mins}' if mins else 'UNKNOWN (not found in code)'

    def at(k):
        return f'{n * k:g} min' if n is not None else 'unknown'

    svc = src('ai/service.py')
    chat_len = first_match('routes/chat.py', r'text\[:(\d+)\]')
    g_raw = getattr(guard, 'MAX_RAW_CHARS', None)
    g_chat = getattr(guard, 'FIELD_LIMITS', {}).get('chat') if guard is not None else None
    g_budget = getattr(guard, 'BUDGET', None)
    ai_page = src('templates/how_ai_works.html')
    model_first, fixed_first = crisis_reply_mode() == 'model', crisis_reply_mode() == 'fixed'
    crisis_cond = excerpt('ai/service.py', r'^\s*crisis = ', limit=1)
    helpline_cond = excerpt('ai/service.py', r'show_helplines = ', limit=1)
    friend_cap = excerpt('ai/service.py', r"score = min\(score, 6\)", limit=1)
    soft_noalert = True
    calls = []
    for rel in ('routes/chat.py', 'routes/patient.py', 'app.py', 'utils/crisis.py'):
        for ln in excerpt(rel, r'(?<!def )(?:try_)?record_crisis\('):
            if 'def ' not in ln:
                calls.append(ln)
    providers_q = excerpt(crisis, r"User\.role == 'provider'", limit=1)
    send_cond = excerpt(crisis, r'level >= 2 and target', limit=1)
    mail_subject = [t for _, _, t in function_strings(crisis, {'crisis_escalate'}, 20) if 'Unacknowledged' in t]
    notif = [t for _, _, t in function_strings(crisis, {'crisis_alert', 'crisis_escalate'}, 25)
             if 'student' in t.lower() and 'Unacknowledged' not in t and 'Event id' not in t]
    cm = re.search(r'class CrisisEvent\(db\.Model\):(.*?)\n\n\n', src('models.py'), re.S)
    cols = re.findall(r'^\s{4}(\w+) = db\.Column', cm.group(1), re.M) if cm else []
    has_followup = any(c for c in cols if re.search(r'follow|closed|status|resolved|contacted', c))
    no_hours = not re.search(r'hour|weekday|business|timezone|working', src(crisis), re.I)
    no_sms = not re.search(r'twilio|sms|whatsapp|fcm|push_notification|webpush', src(crisis) + src('utils/mailer.py'), re.I)
    sev_probe = {}
    if sev is not None:
        for lvl, probe in (('crisis', 'i want to die'), ('friend', 'my friend wants to die'),
                           ('soft', "i don't want to die"), ('none', 'hello how are you')):
            sev_probe[lvl] = (sev.classify(probe), sev.heuristic_severity(probe), probe)
    helplines = load('helplines_flow', 'utils/helplines.py')
    hl = [f"{h['name']}: {h['number']} ({h['hours']})" for h in helplines.HELPLINES] if helplines else ['UNKNOWN']
    phq = scoring.score_phq9([0] * 8 + [1]) if scoring else {}
    sev_thresholds = ''
    if scoring is not None:
        pg = probe_bands(scoring.score_phq9, 9, 27)
        gg = probe_bands(scoring.score_gad7, 7, 21)
        ps = min((lo for lo, hi, (b, s) in pg if s), default=None)
        gs = min((lo for lo, hi, (b, s) in gg if s), default=None)
        sev_thresholds = f'PHQ-9 total >= {ps} or GAD-7 total >= {gs}'

    p = [md_header('Safety flow: what happens when someone may be at risk', stamp, commit, dirty), '']
    p += ['This is the step list for a clinician or lawyer to check. Each fact is read from the code at export time; where '
          'the code could not be read the text says UNKNOWN. Paths are relative to the project root.', '']
    p += ['## 0. Constants read from code and environment defaults', '',
          '| Constant | Value | Source |', '|---|---|---|',
          f'| Escalation interval (env `CRISIS_ESCALATE_MINUTES`) | {mins_s} min | utils/crisis.py `_minutes()` |',
          f'| Escalation levels | 1 to {max_level} (level 0 is the first notification) | utils/crisis.py `MAX_LEVEL` |',
          f'| Alert job retry ceiling | {attempts or "UNKNOWN"} attempts | utils/crisis.py `record_crisis` |',
          f'| Job retry backoff | full jitter, base {jints.get("BACKOFF_BASE", "?")} s, cap {jints.get("BACKOFF_CAP", "?")} s | utils/jobs.py |',
          f'| Worker poll interval | {poll or "?"} s | utils/jobs.py `run_worker` |',
          f'| Job lock timeout (env `JOB_LOCK_TIMEOUT`) | {lock or "?"} s | utils/jobs.py |',
          f'| In-process worker (env `JOBS_INPROCESS`) default | {jobs_default} only when FLASK_ENV=production | utils/jobs.py `init_jobs` |',
          '| Escalation email recipient | env `CRISIS_ESCALATION_EMAIL` (one address, unset by default) | utils/crisis.py |',
          '| SMTP | env `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (unset by default) | utils/mailer.py |',
          f'| Detector severity values | ' + '; '.join(f'{k}: {v[1]}' for k, v in sev_probe.items()) + ' (probe sentences) | ai/severity.py `heuristic_severity` |',
          f'| Chat text checked by the rule-based floor | up to {g_raw} characters | utils/llm_guard.py `MAX_RAW_CHARS` |'
          if guard is not None else f'| Chat text cut before checking | {chat_len or "unknown"} characters | routes/chat.py |',
          f'| Chat text sent to the model (after clean-up) | up to {g_chat} characters | utils/llm_guard.py `FIELD_LIMITS` |'
          if guard is not None else '| Chat text sent to the model | not read (utils/llm_guard.py missing) | |',
          f'| Per-user model budget (env `AI_DAILY_LIMIT`, `AI_BURST_LIMIT`) | {getattr(g_budget, "daily", "?")} per day, '
          f'{getattr(g_budget, "burst", "?")} per minute | utils/llm_guard.py `UserBudget` |'
          if guard is not None else '| Per-user model budget | none (utils/llm_guard.py missing) | |',
          f'| Assessment alert thresholds | PHQ-9 item 9 >= 1, or {sev_thresholds} | ai/scoring.py |', '',
          'The exporter ignores the environment of the machine it runs on. Production may set different values: read the real '
          'production configuration before relying on the timeline.', '']
    p += ['## 1. The rule-based floor (runs first, never calls a model)', '',
          '`ai/severity.py::classify(text)` returns one of four classes:', '',
          '| Class | Meaning | Detector severity | Chat | Journal |', '|---|---|---|---|---|']
    for lvl, label in (('crisis', 'first-person self-harm language'), ('friend', 'someone else is at risk'),
                       ('soft', 'negated or ambiguous distress'), ('none', 'nothing found')):
        v = sev_probe.get(lvl, ('', '?', ''))
        c, j = outcome_text(lvl)
        p.append(f'| {lvl} | {label} | {v[1]} | {c} | {j} |')
    p += ['', 'The full phrase list is in `crisis_phrases.csv`; sentences and the detector output are in `crisis_test_cases.csv`.', '']
    p += ['## 2. Flow A: chat message (web chat, `POST /api/chat`)', '',
          '1. The student must be logged in; the user id comes from the session, never from the request.',
          ('2. The message is bounded (limit in section 0) and passed to `ai/service.py::ask_with_severity`.' if guard is None else
           '2. The message is bounded to the first limit in section 0 and passed to `ai/service.py::ask_with_severity`; the model only ever '
           'sees the cleaned, shorter text.'),
          '3. The rule-based class and severity are computed first, on the full bounded text, before anything else. ' +
          ('Injection markers are detected but this only hardens the prompt, it never changes the floor. A per-user budget decides whether '
           'the model is called at all; over budget, a crisis message is still answered by the floor. ' if guard is not None else '') +
          'Then the model (Gemini) is asked for a reply and its own severity. If the model fails, times out or is blocked, the rule-based '
          'result still stands.',
          f'4. Final severity is the higher of the rule-based and model severities. Decision line in code: `{(crisis_cond or ["NOT FOUND"])[0]}`.',
          f'   Friend class caps severity: `{(friend_cap or ["NOT FOUND"])[0]}`.',
          f'5. Helplines are attached when: `{(helpline_cond or ["NOT FOUND"])[0]}`.',
          '6. Which reply text is shown during a crisis:']
    if model_first:
        guard_txt = (' If the output guard blocks the model reply on a risk path (dosage, diagnosis stated as fact, method details, '
                     'promises, leaks), the fixed text is used instead.' if guard is not None else '')
        p += ['   - AS IMPLEMENTED: the model-written reply is shown during a crisis if the model returned a usable one; the fixed '
              '`CRISIS_REPLY` is used when the model gave nothing usable.' + guard_txt + ' Clinician note: the crisis wording is therefore '
              'not always the fixed text. ' + ('The public page `/ai` (templates/how_ai_works.html) says a fixed reply is shown "whatever the model wrote"; '
              'that sentence and the code disagree and the owner must resolve it before any claim is made.' if 'whatever the model wrote' in ai_page else
              'Check that the public page `/ai` (templates/how_ai_works.html) describes this accurately.')]
    elif fixed_first:
        p += ['   - AS IMPLEMENTED: the fixed `CRISIS_REPLY` is shown whenever the class is crisis.']
    else:
        p += ['   - UNKNOWN: the reply-selection code could not be matched by the exporter. Read ai/service.py.']
    p += [f'7. If the final decision is crisis, `routes/chat.py` writes a `CrisisEvent` (source `chat`, reason code `chat_self_harm`) '
          'and queues a `crisis_alert` job in one commit. If that write fails, the student still receives the reply and helplines '
          'and the response carries `alert_recorded: false`; an ERROR log line holds ids only.',
          '8. A crisis can also be raised by the model alone (model severity at or above the threshold with no rule hit). '
          'It then creates an alert with the same reason code.',
          '9. Soft and friend classes show helplines but create NO alert and NO counsellor notification.',
          '10. Legacy socket chat (`app.py` event `chat_message`): crisis text gets the fixed `CRISIS_REPLY` and '
          'an event with severity 9; the helplines appear inside that reply text.', '',
          'Calls that create events (verbatim):', ''] + ['    ' + c for c in calls] + ['']
    p += ['## 3. Flow B: journal entry', '',
          '1. Title and content are joined and checked with `utils/crisis.py::text_is_crisis`, which is true only for class crisis. '
          'Friend and soft classes are NOT flagged in journals.',
          '2. If crisis: the entry is saved and a `CrisisEvent` (source `journal`, severity 9, reason `journal_self_harm`) plus a '
          '`crisis_alert` job are written in the same transaction as the entry. If the write fails the student sees an error message '
          'and still sees the helplines.',
          '3. The student sees a warning message with the helplines (strings below). No points are awarded for that entry.',
          '4. The AI suggestion for a crisis entry is a fixed text with helplines; no model is called for it.', '']
    p += ['## 4. Flow C: PHQ-9 and GAD-7 (`POST /api/save-assessment`)', '',
          '1. The score is always recomputed on the server from the item answers; a client-sent score is ignored.',
          f'2. An alert is raised when PHQ-9 item 9 is answered 1, 2 or 3 (reason `phq9_item9_positive`, severity 9), or when the total is severe '
          f'({sev_thresholds}; reason `phq9_severe` or `gad7_severe`, severity 7). A skipped item 9 is unanswered and raises nothing.',
          '3. For an alert, the explanation text is fixed (no model call) and the response carries `crisis: true` plus the helplines; '
          'the assessment and the `CrisisEvent` commit together (all or nothing). If saving fails the student still gets the fixed text and helplines.',
          '4. Event source is `phq9` for GAD-7 events as well (the database allows only chat, phq9, journal).',
          '5. No points, badges or streaks are attached to any score.',
          '6. Moderate scores (PHQ-9 10 to 19, GAD-7 10 to 14) raise no alert and create no counsellor task. See `assessment_bands.csv`.', '']
    p += ['## 5. Alert pipeline and escalation timeline (after any event above)', '',
          '| Time | What happens | Who is told | How |', '|---|---|---|---|',
          '| T0 | Event row and `crisis_alert` job committed | nobody yet | database |',
          f'| T0 + a few seconds (worker poll {poll or "?"} s) | `crisis_alert` job runs | every provider account whose institution text equals the student\'s | in-app notification only |',
          f'| T0 + {at(1)} | Level 1, only if nobody acknowledged | same providers | in-app notification again |',
          f'| T0 + {at(2)} | Level 2 | same providers, plus one configured address | in-app notification; email only if `CRISIS_ESCALATION_EMAIL` and SMTP are set |',
          f'| T0 + {at(3)} | Level 3 (last) | same as level 2 | in-app notification and email as above; then an ERROR log line; no further steps |', '',
          'Acknowledging the event on the provider dashboard stops the chain at the next step.', '',
          f'Provider selection in code: `{(providers_q or ["NOT FOUND"])[0]}` (exact match on the free-text institution field; a typo or '
          'a different spelling means nobody is notified).',
          f'Email condition: `{(send_cond or ["NOT FOUND"])[0]}`.', '']
    if notif:
        p += ['Notification text counsellors see:', ''] + [f'> {t}' for t in notif] + ['']
    if mail_subject:
        p += ['Escalation email subject: ' + '; '.join(f'`{m}`' for m in mail_subject), '',
              'Email body holds the institution name, event id and time only. It never holds the student message.', '']
    p += ['Providers of the institution can also see all unacknowledged events on their dashboard without any assignment, and every '
          'acknowledgement is written to the audit log (`routes/provider.py`).', '']
    p += ['## 6. What the code does NOT do (read from the code, verify with the owner)', '']
    p += [f'- No out-of-hours logic: {"no hour, weekday or timezone handling was found in utils/crisis.py" if no_hours else "UNKNOWN, time-related words exist in utils/crisis.py; read it"}. '
          'An alert at 02:00 follows the same timeline as one at 14:00 and waits for a counsellor to log in.',
          f'- No SMS, WhatsApp, phone call or push notification: {"none found in the alert code" if no_sms else "UNKNOWN, matching words found; read the code"}.',
          '- Level 0 and level 1 reach counsellors only as in-app notifications. The only outbound message is the level 2 and 3 email to one configured address.',
          '- No notification to a guardian, hostel warden, college management or police.',
          f'- No follow-up workflow: the CrisisEvent columns are {", ".join(cols) or "UNKNOWN"}. '
          f'{"A column that looks like follow-up state exists; check it." if has_followup else "There is no contacted, closed or follow-up field, so the three-session follow-up from the UGC draft is not tracked."}',
          '- No merging of repeat alerts: each flagged message or entry creates its own event and notifications.',
          '- No 24x7 human behind the alerts is built into the product. Nobody is paged.',
          '- A model failure never removes the helplines, but a database failure can lose the alert (the student is still shown help).', '']
    p += ['## 7. Text the student sees (quoted from the code)', '']
    env = module_strings('ai/service.py')
    for nm in sorted(k for k in env if k.endswith('_REPLY')):
        p += [f'`ai/service.py::{nm}`', '', f'> {env[nm]}', '']
    for rel, funcs, label in (('ai/service.py', {'generate_journal_insights'}, 'Journal suggestion text for a crisis entry'),
                              ('routes/patient.py', {'patient_journal'}, 'Journal page messages'),
                              ('routes/patient.py', {'api_save_assessment'}, 'Assessment result text when an alert is raised'),
                              ('routes/chat.py', {'chat_handler'}, 'Chat API messages')):
        found = [(f, ln, t) for f, ln, t in function_strings(rel, funcs, 40)
                 if re.search(r'alone|painful|danger|screening result|Reach out|trusted|helpline|Free support|Something went wrong', t)]
        if found:
            p += [f'{label} (`{rel}`):', '']
            for f, ln, t in found:
                p += [f'> `{rel}:{ln}` {t}', '']
    js = src('static/js/inline_extracted/chat_inline_1.js')
    m = re.search(r'function showCrisisBanner\(.*?\n  }\n', js, re.S)
    if m:
        lines = re.findall(r"el\('p', null, '([^']+)'\)", m.group(0)) + re.findall(r"placeholder = '([^']+)'", m.group(0))
        p += ['Chat crisis banner (`static/js/inline_extracted/chat_inline_1.js`, function `showCrisisBanner`):', ''] + \
             [f'> {t}' for t in lines] + ['']
    p += ['Helplines shown (`utils/helplines.py`, one config for the whole app):', ''] + [f'- {h}' for h in hl] + \
         ['', 'Last verified in code: ' + (getattr(helplines, 'LAST_VERIFIED', 'UNKNOWN') if helplines else 'UNKNOWN') +
          '. See `helplines.csv` for the verification status of each number.', '']
    p += ['## 8. Drift checks (facts this file relies on, checked at export time)', '', '| Check | Result |', '|---|---|']
    for d, ok in CHECKS:
        p.append(f"| {d} | {'ok' if ok else 'FAILED: re-read the code before using this file'} |")
    write_text(out, 'safety_flow.md', '\n'.join(p))


def build_manifest(out, stamp, commit, dirty, files):
    p = [md_header('Generated review data: manifest', stamp, commit, dirty), '', '## Files', '',
         '| File | Rows or lines | Purpose |', '|---|---|---|']
    purposes = {'crisis_phrases.csv': 'Every phrase and pattern the detector uses; clinician columns blank',
                'crisis_test_cases.csv': 'Every test sentence with the detector output; clinician columns blank',
                'safety_flow.md': 'Step list: detection, replies, events, jobs, notifications, timeline',
                'assessment_bands.csv': 'PHQ-9 and GAD-7 cut-offs and the item 9 rule as implemented',
                'ai_prompt_snapshot.md': 'System prompt and refusal rules as implemented (canary redacted)',
                'helplines.csv': 'Helpline numbers in the app and their verification status',
                'tabletop_scenarios.csv': 'The 15 tabletop scenarios with live detector output'}
    for name in sorted(files):
        p.append(f'| {name} | {files[name]} | {purposes.get(name, "")} |')
    p += ['', '## Code fingerprint (sha256, first 16 hex, line endings normalised)', '', '| File | Fingerprint |', '|---|---|']
    p += [f'| {rel} | {h} |' for rel, h in fingerprints()]
    p += ['', 'A reviewer signing a page must copy the git commit above. If the working tree is not clean, also copy the '
          'fingerprints: the commit alone does not identify what was reviewed.', '', '## Notes from this run', '']
    p += [f'- {n}' for n in NOTES] or ['- none: every module and file was found']
    write_text(out, 'MANIFEST.md', '\n'.join(p))


def count_lines(path):
    with open(path, encoding='utf-8-sig') as f:
        return sum(1 for _ in f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'review', 'generated'))
    ap.add_argument('--timestamp', default=None, help='fixed UTC timestamp for reproducible output')
    args = ap.parse_args(argv)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    stamp = args.timestamp or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    commit, dirty = git_info()

    sev = load('severity', 'ai/severity.py')
    scoring = load('scoring', 'ai/scoring.py')
    helplines = load('helplines', 'utils/helplines.py')
    added = False
    if helplines is not None and 'utils.helplines' not in sys.modules:
        sys.modules['utils.helplines'], added = helplines, True  # llm_guard imports it by package name
    guard = load('llm_guard', 'utils/llm_guard.py')
    if added:
        sys.modules.pop('utils.helplines', None)

    steps = [
        ('crisis_phrases.csv', lambda: build_phrases(out, sev)),
        ('crisis_test_cases.csv', lambda: build_cases(out, sev)),
        ('assessment_bands.csv', lambda: build_bands(out, scoring)),
        ('helplines.csv', lambda: build_helplines(out, helplines)),
        ('tabletop_scenarios.csv', lambda: build_tabletop(out, sev, scoring)),
        ('ai_prompt_snapshot.md', lambda: build_prompt_snapshot(out, stamp, commit, dirty, guard)),
        ('safety_flow.md', lambda: build_flow(out, stamp, commit, dirty, sev, scoring, guard)),
    ]
    for name, fn in steps:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - one broken section must not stop the others
            note(f'{name} could not be built ({type(exc).__name__}: {str(exc)[:120]}); a placeholder was written')
            target = os.path.join(out, name)
            if not os.path.exists(target) or os.path.getsize(target) == 0:
                write_text(out, name, f'NOT EXPORTED: {name} failed with {type(exc).__name__}. See MANIFEST.md.')
    files = {n: count_lines(os.path.join(out, n)) for n, _ in steps if os.path.exists(os.path.join(out, n))}
    build_manifest(out, stamp, commit, dirty, files)
    print(f'Wrote {len(files) + 1} files to {out}')
    print(f'Git commit: {commit}')
    print(f'Notes: {len(NOTES)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
