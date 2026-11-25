"""Mood -> curated YouTube search/video mapping, built from DB tracks or a local dataset file."""
import logging
import os

from flask import jsonify

logger = logging.getLogger('app')  # same logger (and file handler) the routes used inside app.py
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


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
