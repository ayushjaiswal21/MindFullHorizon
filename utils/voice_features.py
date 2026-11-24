"""Acoustic measurements for voice logs. The audio is analysed and thrown away: only the numbers are stored.

librosa/numpy (requirements/voice.txt) are optional and imported inside `extract_features`, never at startup.
"""
import logging
import os
import tempfile
from importlib.util import find_spec

logger = logging.getLogger('app')
LIBROSA_AVAILABLE = find_spec('librosa') is not None and find_spec('numpy') is not None


def classify_emotion(audio_features):
    """Rough emotion guess from pitch/energy/zero-crossing features (heuristic, not a clinical signal)."""
    pitch = audio_features.get('mean_pitch', 0)
    energy = audio_features.get('mean_energy', 0)
    zcr = audio_features.get('mean_zcr', 0)
    if pitch > 200 and energy > 0.1:
        return 'happy'
    if pitch and pitch < 150 and energy < 0.05:
        return 'sad'
    if zcr > 0.1:
        return 'stressed'
    if 150 <= pitch <= 200 and 0.05 <= energy <= 0.1:
        return 'calm'
    return 'neutral'


def extract_features(audio_file, ext):
    """Return (features dict, emotion) for an uploaded werkzeug file. Never raises on bad audio.

    librosa wants a path for mp3/ogg, so the bytes go to a temp file that is deleted in `finally`
    (nothing is kept, nothing is served).
    """
    if not LIBROSA_AVAILABLE:
        return {}, 'neutral'
    path = None
    try:
        import librosa
        import numpy as np
        with tempfile.NamedTemporaryFile(suffix='.' + ext, delete=False) as tmp:
            path = tmp.name
            audio_file.save(tmp)
        y, sr = librosa.load(path, duration=120)  # max 2 minutes
        features = {'duration': len(y) / sr, 'sample_rate': sr}
        pitches, _ = librosa.piptrack(y=y, sr=sr)
        pitch_values = pitches[pitches > 0]
        if len(pitch_values) > 0:
            features['mean_pitch'] = float(np.mean(pitch_values))
            features['pitch_std'] = float(np.std(pitch_values))
        features['mean_energy'] = float(np.mean(librosa.feature.rms(y=y)))
        features['mean_zcr'] = float(np.mean(librosa.feature.zero_crossing_rate(y)))
        features['mean_spectral_centroid'] = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        return features, classify_emotion(features)
    except Exception:
        logger.warning("Audio feature extraction failed; using neutral")
        return {}, 'neutral'
    finally:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
