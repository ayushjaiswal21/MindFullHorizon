"""Edit-distance-1 fuzzy snap onto the crisis vocabulary (SYNTHESIS.md section 3(a) item a3).

Raise-only layer on top of the deterministic floor (ai/severity.py): it can only add a crisis/friend/soft
result on top of what the exact-match regexes already found, never remove or downgrade one. A hit is tagged
'fuzzy' (vs 'exact') so it stays visible to a counsellor/auditor and is never silently indistinguishable from
a direct regex hit.

Measured basis: docs/research/ai/encoders-nlp.md section 3.2. Method there: respell one word (4+ letters) of a
Hinglish crisis sentence (drop an interior vowel, double "a", "i"->"ee", add "h" after t/d/k/g, drop the final
vowel, swap two letters) across 326 systematic variants of the 27 Hinglish must-trigger cases; the unmodified
floor fired on 39%. Then: "a token not in the known vocabulary and at least 5 letters is snapped to a
crisis-vocabulary token within Levenshtein distance 1 (rapidfuzz); the result is classify-ed and the answer is
the OR of both" - that raised recall to 58% with 0 added false positives on the 57 non-crisis cases in that
experiment. The 4-vs-5 letter note matters: the paper's own example ("marna" -> "mrna") drops a 5-letter word to
4 letters, so this module snaps tokens of 4+ letters (not 5+) to keep that example working; vocabulary words
themselves stay 5+ letters, which is the real guard against noise. Re-running the exact classify() on the
corrected text (not a bare vocabulary-presence check) is what keeps negation ("mujhe marna nahi hai") and
third-party mentions ("mera dost ... marna chahta hai") handled exactly as the floor already handles them -
the research experiment names this as the reason embeddings are unsafe here (encoders-nlp.md section 3.1),
and the same reasoning applies to a naive keyword-presence fuzzy layer.

VOCABULARY NEEDS NATIVE-SPEAKER REVIEW (same status as ai/severity.py's phrase lists, O-20).
Selection rule (conservative, so a near-miss on a borderline phrase does not get the same raise-only power as
one on an unambiguous crisis word): every token of 5+ letters, alphabetic, from
docs/review/generated/crisis_phrases.csv rows where list=='crisis_pattern' AND detector_class_alone=='crisis'
AND language_script=='Hinglish' (read 2026-11-25). That excludes: the friend_pattern/soft_pattern/
third_party_word/negator_word/idiom_exclusion_word rows entirely (different list values, so a near-miss on a
soft or third-party phrase is never raised by this layer); English rows (the measured gain was Hinglish
respellings only, and English spelling is far more regular, so fuzzy-matching English crisis words was judged
not worth the extra false-positive surface); and Hinglish crisis_pattern rows where detector_class_alone is
'none' or blank (these are context-only fragments that do not mean crisis alone, so are not safe standalone
fuzzy targets). Hardcoded below (not read from the CSV at import time) so this module has no runtime file
dependency; regenerate by hand from the CSV if the crisis_pattern/Hinglish rows change materially.
"""
from rapidfuzz.distance import Levenshtein

from ai.severity import classify, heuristic_severity, normalize

# docs/review/generated/crisis_phrases.csv snapshot 2026-11-25: list=crisis_pattern, detector_class_alone=crisis,
# language_script=Hinglish, tokens of 5+ letters split on whitespace from phrase_normalised_form (36 tokens).
VOCAB = frozenset({
    'chahta', 'chahti', 'chuka', 'chuki', 'dikhai', 'dunga', 'dungi', 'hamesha', 'iccha', 'ichha',
    'jeena', 'jeene', 'jeevan', 'jiina', 'jiine', 'jindagi', 'karna', 'khatam', 'khayal', 'khudkushi',
    'khushi', 'kushi', 'loonga', 'loongi', 'lunga', 'lungi', 'marjana', 'marna', 'mujhe', 'sabkuch',
    'sakta', 'sakti', 'suicide', 'suicidekar', 'suicidekarna', 'zindagi',
})
_MIN_TOKEN_LEN = 4  # the shortest a vocab word (5+ letters) can shrink to after one deleted letter


def _snap(token):
    """token unchanged, or the one vocabulary word within Levenshtein distance 1, or None if no match."""
    if len(token) < _MIN_TOKEN_LEN or not token.isalpha() or token in VOCAB:
        return None
    for word in VOCAB:
        if Levenshtein.distance(token, word, score_cutoff=1) <= 1:
            return word
    return None


def fuzzy_correct(text):
    """(corrected_text, hit): corrected_text is severity.normalize(text) with any token within edit distance 1
    of the vocabulary snapped to the vocabulary spelling; hit is True iff at least one token changed. Runs on
    normalize()'s output so clause markers ('|') and the floor's own spelling contractions stay intact."""
    s = normalize(text)
    if not s:
        return s, False
    hit = False
    out = []
    for tok in s.split(' '):
        snapped = _snap(tok) if tok and tok != '|' else None
        if snapped:
            hit = True
            out.append(snapped)
        else:
            out.append(tok)
    return ' '.join(out), hit


_SCORE = {'crisis': 9, 'soft': 5, 'friend': 4}
_ORDER = {'none': 0, 'soft': 1, 'friend': 2, 'crisis': 3}


def classify_with_fuzzy(text):
    """(level, matched_via). matched_via is 'exact' if classify(text) alone already found it, 'fuzzy' if only
    the spelling-corrected text does, 'none' if neither. Raise-only: never returns a level below classify(text)
    alone; the fuzzy branch is classify()-ed on the corrected text (same negation/third-party/idiom guards as
    the exact floor), never a bare vocabulary-presence check."""
    exact = classify(text)
    if exact == 'crisis':
        return exact, 'exact'
    corrected, hit = fuzzy_correct(text)
    fuzzy_level = classify(corrected) if hit else 'none'
    if hit and _ORDER[fuzzy_level] > _ORDER[exact]:
        return fuzzy_level, 'fuzzy'
    return exact, ('exact' if exact != 'none' else 'none')


def classify_and_score(text):
    """(level, severity 0-10, matched_via). severity is the higher of the floor's own heuristic_severity(text)
    and the level this layer settled on (raise-only, same mapping as ai/severity.py::heuristic_severity)."""
    level, matched_via = classify_with_fuzzy(text)
    score = max(heuristic_severity(text), _SCORE.get(level, 0))
    return level, score, matched_via
