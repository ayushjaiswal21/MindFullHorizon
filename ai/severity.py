"""Heuristic crisis detection (English + romanized Hindi). Design: docs/SAFETY_RESEARCH.md.

classify(text) -> 'crisis' | 'friend' | 'soft' | 'none'
  crisis: first-person self-harm statement (never downgraded by the LLM)
  friend: someone else is at risk ("my friend wants to die") -> supportive helping-a-friend path
  soft:   negated or ambiguous distress ("i don't want to die", "this exam is killing me") -> gentle check-in
Phrase lists are test fixtures, not a validated corpus: have a clinician and Hindi speakers review them.
"""
import re
import unicodedata

_CONTRACTIONS = [
    (r'\bcannot\b|\bcan not\b', 'cant'), (r'\bdo not\b', 'dont'), (r'\bwill not\b', 'wont'),
    (r'\bi am\b', 'im'), (r'\bi have\b', 'ive'), (r'\bi would\b', 'id'), (r'\bgonna\b', 'going to'),
    (r'\bwanna\b', 'want to'),
    # Hinglish spelling variants
    (r'\b(?:nahin|nhi|nahee|nai)\b', 'nahi'), (r'\b(?:hoon|hun|hoo|hu+)\b', 'hu'),
    (r'\bcha+h(?:a)?th?([ai])\b', r'chaht\1'), (r'\bja+ne\b', 'jane'), (r'\bja+na\b', 'jana'),
    (r'\b(?:theek|thik|theak)\b', 'thik'), (r'\bmann\b', 'man'), (r'\bjee\b', 'ji'),
]
_NEGATORS = {'not', 'dont', 'never', 'wont', 'isnt', 'arent', 'didnt', 'nahi', 'mat'}
_THIRD = {'friend', 'friends', 'bestfriend', 'roommate', 'roomie', 'classmate', 'brother', 'sister', 'cousin',
          'mom', 'mother', 'dad', 'father', 'someone', 'she', 'he', 'they', 'her', 'him', 'boyfriend',
          'girlfriend', 'dost', 'saheli', 'bhai', 'behen', 'didi', 'usne', 'usko', 'uska', 'uski', 'woh', 'wo'}
_FIRST = {'i', 'im', 'ive', 'id', 'me', 'my', 'myself', 'main', 'mai', 'mujhe', 'mera', 'meri'}

_CRISIS = [re.compile(p) for p in [
    r'\bwants? to (?:die|be dead|kill myself|end it all|end my life)\b',
    r'\b(?:kill|killing|hang|hanging|hurt|hurting|harm|harming|drown|drowning|poison|poisoning|shoot|stab) myself\b',
    r'\b(?:keep )?cutting myself\b|\bcut myself on purpose\b|\bself ?harm\b',
    r'\b(?:end|ending) (?:it all|my (?:own )?life)\b|\b(?:end|ending) it tonight\b',
    r'\btake my own life\b|\bcommit(?:ting)? suicide\b|\bsuicidal\b|\b(?:think\w*|thought\w*) (?:of|about) suicide\b',
    r'\bsuicide (?:plan|note)\b',
    r'\bdont want to (?:be alive|live any ?more|live any longer|wake up|exist)\b',
    r'\bwish (?:that )?i (?:were|was) (?:dead|never born)\b|\bwish (?:i|id) (?:not |never |wouldnt |didnt )?(?:wake|woke) up\b',
    r'\bbetter off (?:without me|dead)\b|\bshould (?:just )?(?:disappear|die)\b|\bdisappear forever\b',
    r'\b(?:too many|all my|all the) (?:pills|tablets)\b|\boverdos(?:e|ing|ed)\b',
    r'\bjump(?:ing)? (?:off|from) (?:the |a |my )?(?:roof|terrace|building|balcony|bridge|window|cliff|hostel)\b',
    r'\b(?:dont see any|no) (?:reason|point) (?:to|in) (?:live|living|go on|going on)\b',
    r'\b(?:is not|isnt) worth living\b|\bnot worth living\b|\bcant go on(?:(?: any ?more| like this)\b|(?= \||$))',
    r'\bgoodbye forever\b|\bthis is my last (?:message|note|text)\b|\bwant out (?:permanently|forever|for good)\b',
    # Hinglish / romanized Hindi (first person: "hu", "mujhe", or a first-person verb)
    r'\b(?:mar ?jana|marna) chaht[ai] hu\b|\bmujhe (?:marna|mar ?jana) hai\b',
    r'\bjeen[ae] nahi chaht[ai](?: hu)?(?! hai)\b|\bjeene ka man nahi\b',
    r'\bab ji nahi sak(?:ta|ti)\b',
    r'\bkhud ko khatam\b|\bapni jaan (?:dena|de du|de dunga|de dungi)\b|\bsuicide kar(?:unga|ungi|na chaht[ai] hu)\b',
    r'\bsab (?:kuch )?khatam kar (?:dena|du|dunga|dungi)\b|\bmere jane se sab thik\b',
    r'\bkhud ?k(?:h)?ushi\b(?! ki)', r'\bdikhai nahi dena chaht[ai](?: hu)?(?: \|)* hamesha ke liye\b',
    # Devanagari (no \b: combining marks break word boundaries)
    r'मरना चाहत[ाी]|जीना नहीं चाहत[ाी]|खुदकुशी|आत्महत्या|अपनी जान द',
]]
# someone else at risk even without a first-person marker ("kill himself", "mera dost marna chahta hai")
_OTHER_RISK = re.compile(
    r'\bkill(?:ed|ing)? (?:him|her|them)sel(?:f|ves)\b|\bend (?:his|her|their) (?:own )?life\b|'
    r'\b(?:marna|mar ?jana) chaht[ai] hai\b|\bsuicide ki baat\b|\bjeen[ae] nahi chaht[ai] hai\b')
_SOFT = re.compile(
    r'\bkilling me\b|\bsuicid\w*\b|\bcant take (?:it|this)(?: any ?more)?\b|\bhopeless\b|\bworthless\b|\bburden\b|\bno hope\b|'
    r'\bgive up\b|\bno point\b|\bcant cope\b|\bcannot cope\b|\bcut myself\b|\bmarna nahi\b|\bdont want to die\b')
_MILD = re.compile(r'\b(?:panic(?: attack)?|overwhelmed|alone|anxious|stressed|exhausted)\b')


def normalize(text):
    s = unicodedata.normalize('NFKC', str(text or '')).lower()
    s = re.sub(r"[’‘`']", '', s)
    s = re.sub(r'[.,;!?:\n]+', ' | ', s)
    s = re.sub(r'[^\w\s|ऀ-ॿ]', ' ', s)
    s = re.sub(r'(.)\1{2,}', r'\1', s)  # "dieeee" -> "die"
    for pat, rep in _CONTRACTIONS:
        s = re.sub(pat, rep, s)
    return re.sub(r'\s+', ' ', s).strip()


def _clause_before(s, pos):
    """Tokens before `pos` in the same clause (clauses are split at '|')."""
    return s[:pos].split('|')[-1].split()


def classify(text):
    s = normalize(text)
    if not s:
        return 'none'
    crisis = friend = soft = False
    for rx in _CRISIS:
        for m in rx.finditer(s):
            before = _clause_before(s, m.start())
            if _NEGATORS & set(before[-4:]):
                soft = True  # negated: downgrade to a soft check-in, never drop
            elif not _FIRST & set(before[-1:] + m.group().split()[:1]) and _THIRD & set(before[-6:]):
                friend = True
            else:
                crisis = True
    if crisis:
        return 'crisis'
    if friend or _OTHER_RISK.search(s):
        return 'friend'
    return 'soft' if soft or _SOFT.search(s) else 'none'


def heuristic_severity(text):
    """0-10. crisis 9, soft check-in 5, friend 4, else count of mild distress words (max 3)."""
    level = classify(text)
    if level == 'crisis':
        return 9
    return {'soft': 5, 'friend': 4}.get(level) or min(3, len(_MILD.findall(normalize(text))))
