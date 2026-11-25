"""Regex-to-phrase enumeration for the crisis detector's patterns, plus phrase categorisation."""
import re

try:
    import re._parser as _sp  # Python 3.11+
except ImportError:  # pragma: no cover
    import sre_parse as _sp

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
