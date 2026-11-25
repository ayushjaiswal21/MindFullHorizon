"""Acoustic measurements for voice logs. The audio is analysed and thrown away: only the numbers are stored.

No tone/emotion label is produced: pitch/energy/ZCR thresholds were measured (see
docs/research/ai/SYNTHESIS.md section 1.1 and 3(c), item c1) to mostly detect voice pitch/sex, not mood, with
no within-person baseline, and are speaker-identifying on top of being invalid. Only `duration` (a harmless,
useful fact) is extracted.

librosa/numpy (requirements/voice.txt) are optional and imported inside `extract_features`, never at startup.
"""
import logging
import os
import tempfile
from importlib.util import find_spec

logger = logging.getLogger('app')
LIBROSA_AVAILABLE = find_spec('librosa') is not None and find_spec('numpy') is not None


def extract_features(audio_file, ext):
    """Return a features dict (currently just `duration` in seconds) for an uploaded werkzeug file. Never raises.

    librosa wants a path for mp3/ogg, so the bytes go to a temp file that is deleted in `finally`
    (nothing is kept, nothing is served).
    """
    if not LIBROSA_AVAILABLE:
        return {}
    path = None
    try:
        import librosa
        with tempfile.NamedTemporaryFile(suffix='.' + ext, delete=False) as tmp:
            path = tmp.name
            audio_file.save(tmp)
        y, sr = librosa.load(path, duration=120)  # max 2 minutes
        return {'duration': len(y) / sr}
    except Exception:
        logger.warning("Audio feature extraction failed")
        return {}
    finally:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
