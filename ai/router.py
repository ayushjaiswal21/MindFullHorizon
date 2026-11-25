"""Lexical intent router: char n-gram TF-IDF match of a student's free-typed chat text against a fixed list of
intents. Pure local text matching, no model call and no network - the text never leaves this process.

Based on the measurement in docs/research/ai/encoders-nlp.md section 3.3 ("3. MEASURED experiments on this
repo" / "Retrieval of vetted answers by Hinglish query"): char n-gram TF-IDF (char_wb 2-4 grams) over short
documents that carry a Hinglish/English alias line scored 0.94 top-1 / 1.00 top-3 on a 16-query Hinglish smoke
test, against 0.50-0.69 for multilingual sentence embeddings on the same queries. See also SYNTHESIS.md
section 3(b) item b3 ("Lexical router + retrieval, replacing off_reply() dead end").

Gated behind CHAT_ROUTER_ENABLED in ai/service.py; only ever called for a message the crisis floor
(ai/severity.py::classify) already classified 'none'. Crisis/friend/soft always win and this module is never
consulted for them - it has no way to downgrade or override a floor decision because it never runs on one.

An "alias" here means a short example phrase (English, Hinglish, or a common misspelling) that a student might
actually type for that intent - the same "aliases" concept the research measured against a document's title.
"""
import math
import re
from collections import Counter, namedtuple

CONFIDENCE_THRESHOLD = 0.20  # below this: return a clarifying menu instead of guessing (tuned on tests/test_chat_router.py)
MENU_SIZE = 3

Intent = namedtuple('Intent', 'id label aliases')
RouterResult = namedtuple('RouterResult', 'matched intent_id score candidates')  # candidates: [(intent_id, label), ...]

# ~15-20 fixed intents built from what the app actually offers. Aliases are English, Hinglish and common
# misspellings; kept short on purpose (this is a lexical match, not a sentence encoder).
INTENTS = (
    Intent('mood_checkin', 'Log your mood', (
        'log my mood', 'track my mood', 'how do i log mood', 'mood tracker', 'mood check in',
        'mera mood kaise log karu', 'mood kaise track karu', 'feeling tracker kaha hai')),
    Intent('assessment', 'PHQ-9 / GAD-7 screening', (
        'phq9', 'phq 9', 'gad7', 'gad 7', 'take the assessment', 'depression test', 'anxiety test',
        'screening questionnaire', 'assessment kaise le', 'depression ka test', 'anxiety ka test kahan hai')),
    Intent('journal', 'Write in your journal', (
        'write in my journal', 'journal entry', 'diary', 'open my journal', 'journal likhna hai',
        'diary kaise likhu', 'journal kahan hai', 'mujhe likhna hai')),
    Intent('breathing', 'Breathing guide', (
        'breathing exercise', 'breathing guide', 'how to breathe', 'calm breathing', 'saans lena',
        'breathing wala exercise', 'sans ki exercise', 'breath exercise kaha hai')),
    Intent('grounding', 'Grounding exercise', (
        'grounding exercise', 'grounding technique', '5 4 3 2 1', 'panic attack help',
        'grounding kya hota hai', 'panic ho raha hai kya karu', 'grounding exercise kaise kare')),
    Intent('sleep_log', 'Sleep log', (
        'sleep log', 'cant sleep', 'track my sleep', 'log my sleep', 'insomnia',
        'neend nahi aa rahi', 'sleep kaise log karu', 'raat ko neend nahi aati')),
    Intent('safety_plan', 'Safety plan', (
        'safety plan', 'write a safety plan', 'crisis plan', 'what is a safety plan',
        'safety plan kya hai', 'apna safety plan banana hai')),
    Intent('goals', 'Goals', (
        'my goals', 'set a goal', 'goal tracker', 'goals page',
        'goal kaise set karu', 'apna goal banana hai')),
    Intent('booking', 'Book a counsellor', (
        'book a counsellor', 'book an appointment', 'talk to a counsellor', 'see a counsellor',
        'schedule a session', 'counsellor se baat karni hai', 'appointment kaise book karu',
        'counsellor se milna hai')),
    Intent('medication_log', 'Medication log', (
        'medication log', 'log my medicine', 'track my medicine', 'my prescriptions',
        'dawai ka log', 'medicine kaise log karu', 'meri dawai')),
    Intent('digital_detox', 'Digital detox', (
        'digital detox', 'screen time', 'reduce phone use', 'phone addiction',
        'phone kam use karna hai', 'screen time kam karna hai', 'detox kya hai')),
    Intent('music', 'Music', (
        'relaxing music', 'calming music', 'music page', 'listen to music',
        'gana sunna hai', 'music kahan hai', 'relax karne wala music')),
    Intent('about_privacy', 'What is Anya / privacy', (
        'who are you', 'what is anya', 'are you a real person', 'is this private',
        'is my data safe', 'who sees my data', 'tum kaun ho', 'ye private hai kya',
        'mera data kaun dekhta hai')),
    Intent('delete_account', 'Delete my account', (
        'delete my account', 'remove my account', 'close my account', 'how to delete account',
        'account delete kaise kare', 'mera account delete karna hai')),
    Intent('general_stressed', 'Feeling stressed or anxious', (
        'i am stressed', 'i feel anxious', 'exam stress', 'feeling overwhelmed', 'panicking',
        'bahut stress hai', 'tension ho rahi hai', 'ghabrahat ho rahi hai', 'bahut anxious hu')),
    Intent('general_lonely', 'Feeling lonely or sad', (
        'i feel lonely', 'i feel sad', 'i miss home', 'homesick', 'feeling low',
        'bahut akela lagta hai', 'ghar ki yaad aa rahi hai', 'mann udaas hai')),
)
_BY_ID = {i.id: i for i in INTENTS}

_WORD = re.compile(r'[a-z0-9]+')


def _char_ngrams(text, nmin=2, nmax=4):
    """char_wb-style n-grams: only within words (each word padded with a boundary space), sizes nmin..nmax."""
    grams = []
    for word in _WORD.findall((text or '').lower()):
        padded = f' {word} '
        for n in range(nmin, nmax + 1):
            if len(padded) < n:
                continue
            grams.extend(padded[i:i + n] for i in range(len(padded) - n + 1))
    return grams


def _vectorize(grams, idf):
    tf = Counter(grams)
    vec = {g: (1 + math.log(c)) * idf(g) for g, c in tf.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {g: v / norm for g, v in vec.items()}


def _build_index():
    doc_grams = {intent.id: _char_ngrams(' '.join(intent.aliases)) for intent in INTENTS}
    df = Counter()
    for grams in doc_grams.values():
        for g in set(grams):
            df[g] += 1
    n_docs = len(doc_grams) or 1

    def idf(g):
        return math.log((1 + n_docs) / (1 + df.get(g, 0))) + 1
    vectors = {iid: _vectorize(grams, idf) for iid, grams in doc_grams.items()}
    return idf, vectors


_IDF, _VECTORS = _build_index()


def _score_all(text):
    vec = _vectorize(_char_ngrams(text), _IDF)
    if not vec:
        return []
    scores = [(iid, sum(v * dvec.get(g, 0.0) for g, v in vec.items())) for iid, dvec in _VECTORS.items()]
    scores.sort(key=lambda pair: -pair[1])
    return scores


def match(text, threshold=CONFIDENCE_THRESHOLD, menu_size=MENU_SIZE):
    """Best-matching intent for free-typed text, or a clarifying menu when nothing is confident enough.

    Returns RouterResult(matched, intent_id, score, candidates). `candidates` is only populated when
    matched is False: up to `menu_size` (intent_id, label) pairs for a clarifying quick-reply menu."""
    scores = _score_all(text)
    if not scores or scores[0][1] < threshold:
        top = [(iid, _BY_ID[iid].label) for iid, _ in scores[:menu_size]]
        return RouterResult(False, None, scores[0][1] if scores else 0.0, top)
    return RouterResult(True, scores[0][0], scores[0][1], [])


def label_for(intent_id):
    intent = _BY_ID.get(intent_id)
    return intent.label if intent else None
