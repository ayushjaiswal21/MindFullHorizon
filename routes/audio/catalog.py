"""Mood-filtered catalog listing of local binaural-beats audio files (frequency/type/brainwave matching)."""
import logging
import os

from flask import jsonify, request, url_for

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Enhanced mood mapping with more comprehensive keywords and frequency ranges
MOOD_KEYWORDS = {
    'calm': {
        'keywords': ['delta', 'theta', 'calm', 'relax', 'peace', 'meditat', 'sleep', 'rest'],
        'brainwaves': ['delta', 'theta'],
        'freq_range': (0.5, 8.0),  # Delta: 0.5-4 Hz, Theta: 4-8 Hz
        'priority_freq': [2.0, 4.0, 6.0]
    },
    'focus': {
        'keywords': ['alpha', 'beta', 'focus', 'concentr', 'study', 'work', 'attent', 'alert'],
        'brainwaves': ['alpha', 'beta'],
        'freq_range': (8.0, 30.0),  # Alpha: 8-12 Hz, Beta: 12-30 Hz
        'priority_freq': [10.0, 12.0, 15.0, 20.0]
    },
    'anxious': {
        'keywords': ['theta', 'delta', 'anxiety', 'stress', 'tension', 'worry', 'calm', 'sooth'],
        'brainwaves': ['theta', 'delta'],
        'freq_range': (0.5, 8.0),
        'priority_freq': [4.0, 6.0, 8.0]
    },
    'happy': {
        'keywords': ['alpha', 'gamma', 'happy', 'joy', 'uplift', 'positive', 'energiz', 'boost'],
        'brainwaves': ['alpha', 'gamma'],
        'freq_range': (8.0, 100.0),  # Alpha: 8-12 Hz, Gamma: 30+ Hz
        'priority_freq': [10.0, 40.0, 60.0]
    },
    'sad': {
        'keywords': ['theta', 'delta', 'sad', 'melanchol', 'blue', 'depress', 'comfort', 'heal'],
        'brainwaves': ['theta', 'delta'],
        'freq_range': (0.5, 8.0),
        'priority_freq': [4.0, 6.0]
    },
    'angry': {
        'keywords': ['delta', 'theta', 'anger', 'rage', 'frustrat', 'calm', 'cool', 'release'],
        'brainwaves': ['delta', 'theta'],
        'freq_range': (0.5, 8.0),
        'priority_freq': [2.0, 4.0, 6.0]
    }
}


def _parse_track_info(filename):
    # Example names:
    # Alpha_12_Hz.mp3
    # Alpha_10_Hz_Isochronic_Pulses.mp3
    # Alpha_12_Hz_Solfeggio_396_Hz.mp3
    try:
        base = os.path.splitext(filename)[0]
        parts = base.split('_')
        info = {
            'brainwave': None,
            'frequency': None,
            'type': 'pure',  # pure|isochronic|solfeggio
            'solfeggio_frequency': None,
            'label': filename,
            'length_hint': 'short'  # long for solfeggio (15m), others are usually short
        }
        if parts:
            bw = parts[0].lower()
            if bw in ('alpha', 'beta', 'delta', 'gamma', 'theta'):
                info['brainwave'] = bw
        # Find main Hz
        for i, p in enumerate(parts):
            if p.lower() == 'hz' and i > 0:
                try:
                    info['frequency'] = float(parts[i - 1])
                except Exception:
                    pass
        name_l = filename.lower()
        if 'isochronic_pulses' in name_l:
            info['type'] = 'isochronic'
        if 'solfeggio' in name_l:
            info['type'] = 'solfeggio'
            info['length_hint'] = 'long'
            # Extract solfeggio frequency
            try:
                # ..._Solfeggio_396_Hz
                idx = parts.index('Solfeggio') if 'Solfeggio' in parts else parts.index('Solfeggio'.lower())
            except Exception:
                idx = -1
            if idx != -1 and idx + 2 < len(parts) and parts[idx + 2].lower() == 'Hz'.lower():
                try:
                    info['solfeggio_frequency'] = float(parts[idx + 1])
                except Exception:
                    pass
        # Build label
        bw_label = (info['brainwave'] or '').capitalize()
        freq_label = f"{int(info['frequency']) if info['frequency'] and info['frequency'].is_integer() else info['frequency']} Hz" if info['frequency'] else ''
        suffix = ''
        if info['type'] == 'isochronic':
            suffix = ' (Isochronic)'
        elif info['type'] == 'solfeggio':
            sf = f" {int(info['solfeggio_frequency']) if info['solfeggio_frequency'] and float(info['solfeggio_frequency']).is_integer() else info['solfeggio_frequency']} Hz" if info['solfeggio_frequency'] else ''
            suffix = f" (Solfeggio{sf})"
        pretty = ' '.join([s for s in [bw_label, freq_label] if s]).strip() + suffix
        info['label'] = pretty or filename
        return info
    except Exception:
        return {
            'brainwave': None,
            'frequency': None,
            'type': 'pure',
            'solfeggio_frequency': None,
            'label': filename,
            'length_hint': 'short'
        }


def _sort_key(item, sort_method):
    if sort_method == 'relevance':
        return (-item.get('relevance_score', 0), item.get('label', 'zzz'))
    elif sort_method == 'frequency_asc':
        return (item.get('frequency') or 1e9, item.get('label', 'zzz'))
    elif sort_method == 'frequency_desc':
        return (-(item.get('frequency') or 0), item.get('label', 'zzz'))
    elif sort_method == 'duration':
        # Solfeggio tracks are typically longer
        length_priority = {'solfeggio': 0, 'isochronic': 1, 'pure': 2}
        return (length_priority.get(item.get('type', 'pure'), 2), item.get('label', 'zzz'))
    elif sort_method == 'brainwave':
        brainwave_order = {'delta': 0, 'theta': 1, 'alpha': 2, 'beta': 3, 'gamma': 4}
        return (brainwave_order.get(item.get('brainwave', 'unknown'), 5), item.get('frequency', 0))
    else:  # default
        # Default: relevance first, then type, then brainwave, then frequency
        type_rank = {'solfeggio': 0, 'isochronic': 1, 'pure': 2}
        return (
            -item.get('relevance_score', 0),
            type_rank.get(item.get('type') or 'pure', 2),
            item.get('brainwave') or 'zzzz',
            item.get('frequency') or 1e9
        )


def api_mood_audio():
    """Return a list of audio URLs for the requested mood, using local audio files only.

    Searches common subdirectories in the dataset ('audio/', 'tracks/').
    Supports additional filtering by frequency range, type, and sorting.

    Response: { success: True, files: [ { url: '/audio/..', filename: '...' }, ... ] }
    """
    data = request.get_json() or {}
    mood = (data.get('mood') or '').strip().lower()
    min_freq = data.get('min_frequency')
    max_freq = data.get('max_frequency')
    filter_type = (data.get('type') or '').strip().lower()
    sort_by = (data.get('sort_by') or 'default').strip().lower()

    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood parameter'}), 400

    base_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset')
    if not os.path.isdir(base_dir):
        return jsonify({'success': False, 'files': []})

    subdirs = ['audio', 'tracks']

    mood_config = MOOD_KEYWORDS.get(mood, {
        'keywords': [mood],
        'brainwaves': [],
        'freq_range': (0.0, 1000.0),
        'priority_freq': []
    })
    keywords = mood_config['keywords']

    matches = []
    for sub in subdirs:
        d = os.path.join(base_dir, sub)
        if not os.path.isdir(d):
            continue
        try:
            for fn in os.listdir(d):
                name_l = fn.lower()
                if not name_l.endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    continue
                # Enhanced matching logic
                meta = _parse_track_info(fn)
                should_include = False

                # Check keyword matching
                if any(kw in name_l for kw in keywords):
                    should_include = True

                # Check brainwave matching
                if meta['brainwave'] and meta['brainwave'].lower() in mood_config['brainwaves']:
                    should_include = True

                # Check frequency range matching
                if meta['frequency'] and mood_config['freq_range']:
                    freq = meta['frequency']
                    min_range, max_range = mood_config['freq_range']
                    if min_range <= freq <= max_range:
                        should_include = True

                if should_include:
                    # Apply additional filters
                    if min_freq is not None and meta['frequency'] and meta['frequency'] < min_freq:
                        continue
                    if max_freq is not None and meta['frequency'] and meta['frequency'] > max_freq:
                        continue
                    if filter_type and filter_type != 'all' and meta['type'] != filter_type:
                        continue

                    rel = f"{sub}/{fn}"
                    # Ensure URL uses forward slashes
                    rel_url = rel.replace('\\', '/').replace('\\', '/')

                    # Calculate relevance score for sorting
                    relevance_score = 0
                    if meta['brainwave'] and meta['brainwave'].lower() in mood_config['brainwaves']:
                        relevance_score += 10
                    if meta['frequency'] and meta['frequency'] in mood_config['priority_freq']:
                        relevance_score += 5
                    if any(kw in name_l for kw in keywords[:3]):  # Prioritize first 3 keywords
                        relevance_score += 3

                    matches.append({
                        'url': url_for('serve_audio', filename=rel_url),
                        'filename': fn,
                        'label': meta['label'],
                        'length_hint': meta['length_hint'],
                        'type': meta['type'],
                        'brainwave': meta['brainwave'],
                        'frequency': meta['frequency'],
                        'solfeggio_frequency': meta['solfeggio_frequency'],
                        'relevance_score': relevance_score
                    })
        except Exception as e:
            logger.debug(f"Failed to scan directory {d}: {e}")

    matches.sort(key=lambda x: _sort_key(x, sort_by))

    return jsonify({'success': True, 'files': matches})
