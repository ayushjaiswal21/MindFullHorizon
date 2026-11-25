"""Heuristic crisis detection (English, romanized Hindi/Hinglish, Devanagari). Design: docs/SAFETY_RESEARCH.md.

WORDLIST NEEDS CLINICIAN AND NATIVE-SPEAKER REVIEW (O-20). Every phrase below is a constructed fixture.
This is the deterministic crisis floor: it runs before and independent of the model and of any injection verdict.

classify(text) -> 'crisis' | 'friend' | 'soft' | 'none'
  crisis: first-person self-harm statement (never downgraded by the LLM)
  friend: someone else is at risk ("my friend wants to die") -> supportive helping-a-friend path
  soft:   negated or ambiguous distress ("i don't want to die", "this exam is killing me") -> gentle check-in
Phrase lists are test fixtures, not a validated corpus: have a clinician and Hindi speakers review them.
"""
import re
import unicodedata

_CONTRACTIONS = [
    (r'\bmy self\b', 'myself'),
    (r'\bcannot\b|\bcan not\b', 'cant'), (r'\bdo not\b', 'dont'), (r'\bwill not\b', 'wont'),
    (r'\bi am\b', 'im'), (r'\bi have\b', 'ive'), (r'\bi would\b', 'id'), (r'\bgonna\b', 'going to'),
    (r'\bwanna\b', 'want to'),
    # Hinglish spelling variants
    (r'\b(?:nahin|nhi|nahee|nai)\b', 'nahi'), (r'\b(?:hoon|hun|hoo|hu+)\b', 'hu'),
    (r'\bcha+h(?:a)?th?([ai])\b', r'chaht\1'), (r'\bja+ne\b', 'jane'), (r'\bja+na\b', 'jana'),
    (r'\b(?:theek|thik|theak)\b', 'thik'), (r'\bmann\b', 'man'), (r'\bjee\b', 'ji'),
]
_NEGATORS = {'not', 'dont', 'never', 'wont', 'isnt', 'arent', 'didnt', 'nahi', 'mat', 'नहीं', 'मत'}
_THIRD = {'friend', 'friends', 'bestfriend', 'roommate', 'roomie', 'classmate', 'brother', 'sister', 'cousin',
          'mom', 'mother', 'dad', 'father', 'someone', 'she', 'he', 'they', 'her', 'him', 'boyfriend',
          'girlfriend', 'dost', 'saheli', 'bhai', 'behen', 'didi', 'usne', 'usko', 'uska', 'uski', 'woh', 'wo',
          'दोस्त', 'सहेली', 'भाई', 'बहन', 'वह', 'वो', 'उसने', 'उसको', 'उसकी', 'उसका'}
_FIRST = {'i', 'im', 'ive', 'id', 'me', 'my', 'myself', 'main', 'mai', 'mujhe', 'mera', 'meri', 'मैं', 'मुझे', 'मेरा', 'मेरी'}

_CRISIS = [re.compile(unicodedata.normalize('NFKC', p)) for p in [
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
    r'\b(?:slit|slash) my (?:wrists?|veins?|throat)\b|\bcut my (?:wrists?|veins?|throat)\b',
    r'\bun ?aliv(?:e|ing) (?:myself|me)\b|\btake my (?:own )?life\b|\b(?:end|ending) everything\b',
    r'\btired of (?:living|being alive)\b|\btired of life\b(?! hack)',
    r'\b(?:ive got|i have|got) (?:a |my )?plan\b.{0,40}\b(?:pills|tablets|rope|noose|knife|blade|gun|poison)\b|\b(?:pills|tablets|rope|noose|blade) (?:are |is )?(?:ready|by my side|next to me)\b',
    r'\bdont want to be here any ?more\b|\b(?:swallow|swallowed|swallowing) (?:all )?(?:the |my |these )?(?:pills|tablets)\b',
    # Hinglish / romanized Hindi (first person: "hu", "mujhe", or a first-person verb)
    r'\b(?:mar ?jana|marna) chaht[ai](?: hu)?(?! hai)\b|\bmujhe (?:marna|mar ?jana) hai\b',
    r'\b(?:jeen[ae]|jiin[ae]|jin[ae]) nahi chaht[ai](?: hu)?(?! hai)\b|\b(?:jeene|jine|jiine) ka (?:koi )?man (?:hi )?nahi\b',
    r'\bab ji nahi sak(?:ta|ti)\b',
    r'\b(?:mujhe|ab) (?:ab )?(?:jeen[ae]|jin[ae]|jiin[ae]) nahi (?:hai|hota|raha)\b',
    r'\bkhud ko khatam\b|\bapni jaan (?:dena|de du|de dunga|de dungi|de dena|de loonga|de lunga)\b',
    r'\bsuicide ?kar ?(?:unga|ungi|na chaht[ai]|loonga|lunga|loongi|lungi|lu|na hai)\b',
    r'\b(?:sab|sabkuch|zindagi|jindagi|jeevan|jaan|apni zindagi|apna jeevan|life) (?:kuch )?(?:ko )?khatam kar (?:dena|lena|du|dunga|dungi|loonga|lunga|loongi|lungi|diya)\b',
    r'\bmere jane se sab thik\b',
    r'\b(?:zindagi|jindagi|jeevan|jeene|jine) se (?:thak|tang aa) (?:gaya|gayi|gai|chuka|chuki)\b',
    r'\bmarn[ae] (?:ka|ki) (?:man|soch|khayal|iccha|ichha)\b(?! nahi)',
    r'\bkhud ?k(?:h)?ushi\b(?! ki)', r'\bdikhai nahi dena chaht[ai](?: hu)?(?: \|)* hamesha ke liye\b',
    # Devanagari (no \b: combining marks break word boundaries). These 4 patterns plus the 1 below in
    # _CRISIS_CAUTIOUS cover all 108 Devanagari-script rows in docs/review/generated/crisis_phrases.csv
    # with zero misses (verified empirically by running every row through classify(), 2026-11-25). SYNTHESIS.md
    # 1.2 called this "unresolved" and estimated 109 rows; the real count is 108, a one-off in that report.
    r'(?:मरना|मर जाना) चाहत[ाीे]|जीना नहीं चाहत[ाीे]|खुदकुशी|आत्महत्या|अपनी जान द|सुसाइड|सुइसाइड',
    r'(?:मुझे|अब) (?:अब )?जीना नहीं है|जीने (?:का|की) (?:मन|इच्छा) (?:ही )?नहीं|मरने (?:का|की) (?:मन|सोच|इच्छा|ख़याल|खयाल)(?! नहीं)',
    r'(?:खुद को|सब कुछ|सबकुछ|सब|ज़िंदगी|जिंदगी|जीवन|अपनी जान) (?:को )?(?:खत्म|ख़त्म) कर',
    r'(?:ज़िंदगी|जिंदगी|जीवन) से थक(?: गया| गई| गयी| चुका| चुकी)',
]]
# idiom-prone: skipped when "se"/laughter/shame words sit just before ("sharam se mar jaunga")
_CRISIS_CAUTIOUS = [re.compile(r'\bmar (?:jaun|jau|jaoon|jaunga|jaungi|jaaun|jaaunga|jaungi)\b'),
                    re.compile(unicodedata.normalize('NFKC', 'मर (?:जाऊं|जाऊँ|जाऊंगा|जाऊंगी|जाउंगा)'))]
_IDIOM_BEFORE = {'se', 'hasi', 'hansi', 'sharam', 'sharm', 'embarrassment', 'laughter', 'darr', 'से', 'हँसी', 'हंसी', 'शर्म'}
# someone else at risk even without a first-person marker ("kill himself", "mera dost marna chahta hai")
_OTHER_RISK = re.compile(
    r'\bkill(?:ed|ing)? (?:him|her|them)sel(?:f|ves)\b|\bend (?:his|her|their) (?:own )?life\b|'
    r'\b(?:marna|mar ?jana) chaht[ai] hai\b|\bsuicide ki baat\b|\bjeen[ae] nahi chaht[ai] hai\b')
_SOFT = re.compile(
    r'\bkilling me\b|\bkms\b|\bsuicid\w*\b|\bcant take (?:it|this)(?: any ?more)?\b|\bhopeless\b|\bworthless\b|\bburden\b|\bno hope\b|'
    r'\bgive up\b|\bno point\b|\bcant cope\b|\bcannot cope\b|\bcut myself\b|\bmarna nahi\b|\bdont want to die\b')
_MILD = re.compile(r'\b(?:panic(?: attack)?|overwhelmed|alone|anxious|stressed|exhausted)\b')


_CONFUSABLES = str.maketrans({  # Cyrillic/Greek lookalikes folded to Latin
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x', 'і': 'i', 'ј': 'j', 'ѕ': 's', 'ԁ': 'd',
    'ο': 'o', 'ι': 'i', 'κ': 'k', 'ν': 'v', 'α': 'a', 'ε': 'e', 'ρ': 'p'})
_LEET = str.maketrans('01345@$7', 'oieasast')
_INVISIBLE_MN = {0x034F, 0x180B, 0x180C, 0x180D} | set(range(0xFE00, 0xFE10))


def strip_invisible(s):
    """Drop format/control characters (zero-width, bidi, tags) that split words and defeat matching."""
    return ''.join(c for c in s if (c in '\n\t\r ' or unicodedata.category(c) not in ('Cf', 'Cc'))
                   and ord(c) not in _INVISIBLE_MN)


def normalize(text):
    s = strip_invisible(unicodedata.normalize('NFKC', str(text or ''))).lower().translate(_CONFUSABLES)
    # leetspeak only inside tokens that mix letters and digits ("k1ll", "su1c1de"); plain numbers are untouched
    s = re.sub(r'(?<=[a-z])[@$](?=[a-z0-9])', lambda m: m.group().translate(_LEET), s)
    s = re.sub(r'\b(?=[a-z0-9]*[a-z])(?=[a-z0-9]*\d)[a-z0-9]+\b', lambda m: m.group().translate(_LEET), s)
    # spaced-out letters ("k i l l  m y s e l f"): runs of 4+ single characters joined by single spaces
    s = re.sub(r'(?<!\S)(?:[a-z0-9] ){3,}[a-z0-9](?!\S)', lambda m: m.group().replace(' ', ''), s)
    s = re.sub(r"[’‘`']", '', s)
    s = re.sub(r'[.,;!?:\n]+', ' | ', s)
    s = re.sub(r'[^\w\s|ऀ-ॿ]', ' ', s)
    s = re.sub(r'(.)\1{2,}', r'\1', s)  # "dieeeee" -> "die"
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
    for rx in _CRISIS_CAUTIOUS:
        for m in rx.finditer(s):
            before = _clause_before(s, m.start())
            if _IDIOM_BEFORE & set(before[-3:]) or _NEGATORS & set(before[-4:]):
                continue
            if not _FIRST & set(before[-1:]) and _THIRD & set(before[-6:]):
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
