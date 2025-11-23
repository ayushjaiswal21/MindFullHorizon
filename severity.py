# /mnt/data/severity.py
SEVERE_KEYWORDS = [
    'suicide','kill myself','end my life','want to die','cant go on',
    'cut myself','self harm','hurt myself','die tonight',
    'no hope','thinking of harming','wish i was dead','planning to'
]
HIGH_RISK_KEYWORDS = ['plan', 'intent', 'means', 'have a gun', 'poison', 'access to']

def heuristic_severity(text: str) -> int:
    if not text:
        return 0
    t = text.lower()
    score = 0
    for kw in SEVERE_KEYWORDS:
        if kw in t:
            score += 6
    for kw in HIGH_RISK_KEYWORDS:
        if kw in t:
            score += 2
    # Increased score for 'hopeless' to meet user expectations
    if 'hopeless' in t:
        score += 3
    for tok in ['worthless','alone','panic','panic attack','overwhelmed','cant cope','cannot cope']:
        if tok in t:
            score += 1
    return min(10, score)