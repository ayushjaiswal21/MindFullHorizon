"""Optional TextBlob sentiment, imported on first use (textblob pulls in nltk, about 0.8 s and 40 MB).

`TextBlob(text)` has the same call shape as the real class; `TEXTBLOB_AVAILABLE` is a cheap
find_spec check, so importing this module never loads textblob or nltk.
"""
from importlib.util import find_spec

TEXTBLOB_AVAILABLE = find_spec('textblob') is not None


def TextBlob(text):  # noqa: N802 (keeps the old call sites unchanged)
    from textblob import TextBlob as _TextBlob
    return _TextBlob(text)
