"""The single source of helpline numbers. Re-verify quarterly (see docs/SAFETY_RESEARCH.md)."""

LAST_VERIFIED = '2026-11'

HELPLINES = [
    {'name': 'Tele-MANAS (Govt. of India)', 'number': '14416', 'tel': '14416', 'hours': '24x7',
     'note': 'Free, about 20 languages. Also 1-800-891-4416.'},
    {'name': 'KIRAN (Ministry of Social Justice)', 'number': '1800-599-0019', 'tel': '18005990019', 'hours': '24x7',
     'note': 'Free mental-health helpline.'},
    {'name': 'Emergency (police, ambulance)', 'number': '112', 'tel': '112', 'hours': '24x7',
     'note': 'If you or someone else is in immediate danger.'},
]
for _h in HELPLINES:
    _h['last_verified'] = LAST_VERIFIED


def get_helplines():
    """A fresh copy, safe to put in a JSON response."""
    return [dict(h) for h in HELPLINES]


def helplines_lines():
    return [f"{h['name']}: {h['number']} ({h['hours']})" for h in HELPLINES]


def helplines_text():
    return ' | '.join(helplines_lines())
