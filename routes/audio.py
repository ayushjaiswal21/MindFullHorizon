"""Music and audio routes moved out of app.py (O-15).

Endpoint names and URLs are unchanged (`url_for('serve_audio')` etc.): they are registered on the app with
`add_url_rule`, not on a blueprint, because a blueprint would prefix every endpoint name.
"""
import json
import logging
import os
from datetime import datetime
from urllib.parse import quote

from flask import jsonify, redirect, render_template, request, send_from_directory, session, url_for

from decorators import api_login_required
from extensions import limiter

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def api_mood_music():
    """Return a curated mapping of moods to YouTube search queries (and optional curated video IDs).

    The frontend can fetch this and either open a search page or use curated video IDs to embed a player.
    """
    # Default static mapping (fallback)
    mood_map = {
        'happy': {'query': 'binaural beats happy uplifting 528hz', 'videos': []},
        'sad': {'query': 'binaural beats sad calming 432hz', 'videos': []},
        'angry': {'query': 'binaural beats anger release calming bass', 'videos': []},
        'calm': {'query': 'binaural beats calm relaxation 432hz mindfulness', 'videos': []},
        'anxious': {'query': 'binaural beats anxiety relief slow tempo 432hz', 'videos': []},
        'focus': {'query': 'binaural beats focus concentration alpha waves 432hz', 'videos': []}
    }

    # Prefer DB-backed tracks if the optional `binaural_tracks` table has entries.
    try:
        from models import BinauralTrack
        db_tracks_exist = BinauralTrack.query.limit(1).first() is not None
    except Exception:
        db_tracks_exist = False

    if db_tracks_exist:
        try:
            from models import BinauralTrack
            # Build mood_map from DB
            mapping = {
                'happy': [], 'sad': [], 'angry': [], 'calm': [], 'anxious': [], 'focus': []
            }
            for t in BinauralTrack.query.all():
                e = (t.emotion or '').lower()
                # Simple heuristic mapping from stored emotion to our mood buckets
                if any(x in e for x in ('happy', 'uplift', 'joy', 'positive')):
                    mapping['happy'].append(t)
                elif any(x in e for x in ('sad', 'melancholy', 'blue')):
                    mapping['sad'].append(t)
                elif any(x in e for x in ('angry', 'anger', 'irritat')):
                    mapping['angry'].append(t)
                elif any(x in e for x in ('calm', 'relax', 'peace')):
                    mapping['calm'].append(t)
                elif any(x in e for x in ('anxious', 'anxiety', 'tense')):
                    mapping['anxious'].append(t)
                elif any(x in e for x in ('focus', 'concentr', 'study', 'attention')):
                    mapping['focus'].append(t)
                else:
                    # fallback: put in calm
                    mapping['calm'].append(t)

            # Convert to response shape using dictionary comprehensions
            resp_map = {
                k: {'query': mood_map[k]['query'], 'videos': []}
                for k in mapping.keys()
            }

            # Process each mood's tracks
            for k in mapping:
                for t in mapping[k]:
                    if t.youtube_id:
                        resp_map[k]['videos'].append({'id': t.youtube_id, 'title': t.title})
                    else:
                        resp_map[k]['query'] = resp_map[k]['query'] + ' ' + t.title

            # Deduplicate
            for k in resp_map:
                seen = set()
                dedup = []
                for it in resp_map[k]['videos']:
                    if it['id'] and it['id'] not in seen:
                        seen.add(it['id'])
                        dedup.append(it)
                resp_map[k]['videos'] = dedup

            return jsonify({'success': True, 'moods': resp_map})

        except Exception as e:
            logger.debug(f"Failed to build mood map from DB tracks: {e}")
            # fall through to file-based parsing/fallback

    # Attempt to enrich mapping from a local copy of the binaural-beats dataset
    # Expected location: ./data/binaural-beats-dataset/ (user can git clone the repo there)
    dataset_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset')
    try:
        if os.path.isdir(dataset_dir):
            # Try common filenames in the dataset
            possible_files = ['tracks.csv', 'dataset.csv', 'tracks.json', 'data.json']
            found = None
            for fn in possible_files:
                path = os.path.join(dataset_dir, fn)
                if os.path.isfile(path):
                    found = path
                    break

            if found:
                # Prefer CSV, otherwise JSON
                if found.lower().endswith('.csv'):
                    import csv
                    with open(found, 'r', encoding='utf-8') as fh:
                        reader = csv.DictReader(fh)
                        for row in reader:
                            # Dataset may have columns like: title, artist, emotion, youtube_id, tags
                            emotion = (row.get('emotion') or row.get('mood') or '').strip().lower()
                            youtube_id = (row.get('youtube_id') or row.get('video_id') or row.get('youtube') or '').strip()
                            title = (row.get('title') or row.get('name') or '').strip()
                            if not emotion:
                                continue

                            # Map dataset emotion labels to our mood keys
                            mapping = {
                                'happy': ['happy', 'uplifting', 'joy', 'positive'],
                                'sad': ['sad', 'melancholy', 'blue'],
                                'angry': ['angry', 'anger', 'irritated'],
                                'calm': ['calm', 'relaxed', 'relaxation', 'peaceful'],
                                'anxious': ['anxious', 'anxiety', 'tense'],
                                'focus': ['focus', 'concentration', 'study', 'attention']
                            }

                            for mood_key, labels in mapping.items():
                                if any(label in emotion for label in labels):
                                    if youtube_id:
                                        mood_map[mood_key]['videos'].append({'id': youtube_id, 'title': title})
                                    else:
                                        # If no direct video id, append title to query suggestions
                                        mood_map[mood_key]['query'] = mood_map[mood_key]['query'] + ' ' + title
                                    break

                else:
                    # JSON file
                    import json
                    with open(found, 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                        # Expect list of tracks
                        items = data if isinstance(data, list) else data.get('tracks') or data.get('data') or []
                        for item in items:
                            emotion = (item.get('emotion') or item.get('mood') or '')
                            if emotion:
                                emotion = emotion.strip().lower()
                            youtube_id = (item.get('youtube_id') or item.get('video_id') or item.get('youtube') or '')
                            title = (item.get('title') or item.get('name') or '')
                            if not emotion:
                                continue

                            mapping = {
                                'happy': ['happy', 'uplifting', 'joy', 'positive'],
                                'sad': ['sad', 'melancholy', 'blue'],
                                'angry': ['angry', 'anger', 'irritated'],
                                'calm': ['calm', 'relaxed', 'relaxation', 'peaceful'],
                                'anxious': ['anxious', 'anxiety', 'tense'],
                                'focus': ['focus', 'concentration', 'study', 'attention']
                            }

                            for mood_key, labels in mapping.items():
                                if any(label in emotion for label in labels):
                                    if youtube_id:
                                        mood_map[mood_key]['videos'].append({'id': youtube_id, 'title': title})
                                    else:
                                        mood_map[mood_key]['query'] = mood_map[mood_key]['query'] + ' ' + title
                                    break

    except Exception as e:
        # Fail gracefully: keep default mapping and log
        logger.debug(f"Failed to load local binaural-beats dataset: {e}")

    # Deduplicate video lists by id
    for k, v in mood_map.items():
        vids = v.get('videos') or []
        seen = set()
        deduped = []
        for it in vids:
            vid = it.get('id')
            if not vid:
                continue
            if vid in seen:
                continue
            seen.add(vid)
            deduped.append(it)
        mood_map[k]['videos'] = deduped

    return jsonify({'success': True, 'moods': mood_map})


def api_play_mood():
    """Attempt to play a binaural track for the requested mood.

    Priority:
      1. Look for local audio files in data/binaural-beats-dataset/audio/ whose filename contains the mood.
         If found, return its /audio/ URL for the browser to play (never launch anything on the server).
      2. If DB has BinauralTrack with youtube_id for the mood, return a YouTube URL for frontend to open.
      3. Otherwise return a YouTube search URL for the mood query.

    Returns JSON: { success: True, action: 'local'|'youtube', url }
    """
    data = request.get_json(silent=True)
    mood = str(data.get('mood') or '').strip().lower() if isinstance(data, dict) else ''

    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood parameter'}), 400

    # 1) local audio folder
    audio_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset', 'audio')
    try:
        if os.path.isdir(audio_dir):
            # look for files containing the mood in filename
            for fn in os.listdir(audio_dir):
                if mood in fn.lower() and fn.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    return jsonify({'success': True, 'action': 'local', 'url': f'/audio/audio/{quote(fn)}'})

    except Exception as e:
        logger.debug(f"Error while searching for local audio files: {e}")

    # 2) DB-backed YouTube id
    try:
        from models import BinauralTrack
        tracks = BinauralTrack.query.filter(BinauralTrack.emotion.ilike(f"%{mood}%")).all()
        if tracks:
            # Prefer tracks with youtube_id
            for t in tracks:
                if t.youtube_id:
                    url = f"https://www.youtube.com/watch?v={t.youtube_id}"
                    return jsonify({'success': True, 'action': 'youtube', 'url': url})
    except Exception:
        pass

    # Removed YouTube fallback. If no local file/DB record found return not found.
    return jsonify({'success': False, 'message': 'No local audio or DB track found for this mood.'}), 404


def serve_audio(filename):
    """Serve audio files from data/binaural-beats-dataset for in-browser playback.

    Supports both 'audio/' and 'tracks/' subdirectories found in common datasets.

    NOTE: This route is intentionally simple. If you deploy publicly, consider adding
    authentication and range requests for large files.
    """
    base_dir = os.path.join(basedir, 'data', 'binaural-beats-dataset')

    # Hosted deploys keep the big mp3s off git: set AUDIO_BASE_URL (e.g. an R2/S3 bucket URL)
    # and any file missing locally is redirected there.
    audio_base = os.environ.get('AUDIO_BASE_URL', '').rstrip('/')
    if audio_base and '..' not in filename.replace('\\', '/').split('/') \
            and not os.path.isfile(os.path.join(base_dir, filename)):
        from urllib.parse import quote
        return redirect(f"{audio_base}/{quote(filename)}")

    if not os.path.isdir(base_dir):
        return jsonify({'success': False, 'message': 'Audio directory not found'}), 404

    # Prevent directory traversal and ensure the file resides within base_dir
    safe_filename = os.path.normpath(filename).replace('\\', '/')
    if safe_filename.startswith('../') or safe_filename.startswith('..\\') or '..' in safe_filename.split('/'):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    full_path = os.path.join(base_dir, safe_filename)
    try:
        full_path = os.path.normpath(full_path)
        # Ensure full_path is inside base_dir
        if not full_path.startswith(os.path.normpath(base_dir)):
            return jsonify({'success': False, 'message': 'Invalid path'}), 400
        # Serve via send_from_directory using base_dir and the relative safe path
        return send_from_directory(base_dir, safe_filename)
    except Exception:
        return jsonify({'success': False, 'message': 'File not found'}), 404


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

    # Enhanced mood mapping with more comprehensive keywords and frequency ranges
    mood_keywords = {
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
    
    mood_config = mood_keywords.get(mood, {
        'keywords': [mood],
        'brainwaves': [],
        'freq_range': (0.0, 1000.0),
        'priority_freq': []
    })
    keywords = mood_config['keywords']

    def parse_track_info(filename):
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
                if bw in ('alpha','beta','delta','gamma','theta'):
                    info['brainwave'] = bw
            # Find main Hz
            for i, p in enumerate(parts):
                if p.lower() == 'hz' and i > 0:
                    try:
                        info['frequency'] = float(parts[i-1])
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
                if idx != -1 and idx + 2 < len(parts) and parts[idx+2].lower() == 'Hz'.lower():
                    try:
                        info['solfeggio_frequency'] = float(parts[idx+1])
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
                meta = parse_track_info(fn)
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

    # Enhanced sorting logic
    def get_sort_key(item, sort_method):
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
    
    matches.sort(key=lambda x: get_sort_key(x, sort_by))

    return jsonify({'success': True, 'files': matches})


def music():
    """Render the music discovery page which allows users to pick a mood and play binaural beats."""
    return render_template('music.html')


def api_log_mood_selection():
    """Log a user's mood music selection for analytics/debugging.

    Accepts JSON: { mood: 'calm', query: '...', video: 'youtube_id' }
    Logging is appended to `mood_selections.log` and written to the application logger.
    """
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    data = request.get_json() or {}
    mood = data.get('mood')
    query = data.get('query')
    video = data.get('video')
    user_id = session.get('user_id')

    if not mood:
        return jsonify({'success': False, 'message': 'Missing mood field'}), 400

    log_entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'user_id': user_id,
        'mood': mood,
        'query': query,
        'video': video,
        'ip': request.remote_addr
    }

    try:
        # Log via application logger for centralized logs
        logger.info(f"Mood selection: {log_entry}")

        # Also append to a simple file for quick analytics without DB migration
        try:
            with open(os.path.join(basedir, 'instance', 'mood_selections.log'), 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as file_err:
            logger.debug(f"Failed to write mood selection to file: {file_err}")

        return jsonify({'success': True, 'message': 'Selection logged'})
    except Exception as e:
        logger.error(f"Error logging mood selection: {e}")
        return jsonify({'success': False, 'message': 'Failed to log selection'}), 500


def register_audio_routes(app):
    app.add_url_rule('/api/mood-music', 'api_mood_music', api_mood_music, methods=['GET'])
    app.add_url_rule('/api/play-mood', 'api_play_mood', api_login_required(api_play_mood), methods=['POST'])
    app.add_url_rule('/audio/<path:filename>', 'serve_audio', serve_audio, methods=['GET'])
    app.add_url_rule('/api/mood-audio', 'api_mood_audio', api_mood_audio, methods=['POST'])
    app.add_url_rule('/music', 'music', music, methods=['GET'])
    app.add_url_rule('/api/log-mood-selection', 'api_log_mood_selection', limiter.limit('30 per hour')(api_log_mood_selection), methods=['POST'])
