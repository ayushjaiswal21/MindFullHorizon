"""
Import binaural beats dataset into the application's database.

Usage:
    python -m scripts.import_binaural_dataset [--dry-run]

This script scans `data/binaural-beats-dataset/` for CSV/JSON files and inserts records
into the `binaural_tracks` table. It avoids duplicates by youtube_id or by title+artist.
"""
import os
import argparse
import json
import csv
from datetime import datetime

from extensions import db

# Import the app module to access Flask app context and models
import importlib, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
app_mod = importlib.import_module('app')
from models import BinauralTrack

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'binaural-beats-dataset')


def find_files(directory):
    supported = []
    for root, _, files in os.walk(directory):
        for fn in files:
            if fn.lower().endswith('.csv') or fn.lower().endswith('.json'):
                supported.append(os.path.join(root, fn))
    return supported


def parse_csv(path):
    rows = []
    with open(path, 'r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows


def parse_json(path):
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    # try to find nested lists
    for key in ('tracks', 'data', 'items'):
        if key in data and isinstance(data[key], list):
            return data[key]
    return []


def normalize_row(row):
    # Normalize common fields
    title = (row.get('title') or row.get('name') or '').strip()
    artist = (row.get('artist') or row.get('composer') or row.get('creator') or '').strip()
    emotion = (row.get('emotion') or row.get('mood') or row.get('tag') or '').strip().lower()
    youtube_id = (row.get('youtube_id') or row.get('video_id') or row.get('youtube') or '').strip()
    tags = None
    if row.get('tags'):
        try:
            tags = json.loads(row.get('tags')) if isinstance(row.get('tags'), str) and row.get('tags').startswith('[') else [t.strip() for t in str(row.get('tags')).split(',') if t.strip()]
        except Exception:
            tags = [t.strip() for t in str(row.get('tags')).split(',') if t.strip()]
    return {
        'title': title,
        'artist': artist,
        'emotion': emotion,
        'youtube_id': youtube_id,
        'tags': tags
    }


def main(dry_run=False):
    if not os.path.isdir(DATA_DIR):
        print(f"Dataset directory not found: {DATA_DIR}")
        return

    files = find_files(DATA_DIR)
    if not files:
        print(f"No CSV/JSON files found in {DATA_DIR}")
        return

    print(f"Found {len(files)} files to import.")

    with app_mod.app.app_context():
        inserted = 0
        skipped = 0
        for f in files:
            print(f"Processing {f}")
            try:
                if f.lower().endswith('.csv'):
                    rows = parse_csv(f)
                else:
                    rows = parse_json(f)
            except Exception as e:
                print(f"  Failed to parse {f}: {e}")
                continue

            for r in rows:
                nr = normalize_row(r)
                if not nr['title']:
                    skipped += 1
                    continue

                # Skip duplicates by youtube_id
                exists = None
                if nr['youtube_id']:
                    exists = BinauralTrack.query.filter_by(youtube_id=nr['youtube_id']).first()
                if not exists:
                    # Or match by title + artist
                    exists = BinauralTrack.query.filter_by(title=nr['title'], artist=nr['artist']).first()

                if exists:
                    skipped += 1
                    continue

                if dry_run:
                    print(f"  Dry-run: would insert: {nr['title']} ({nr['youtube_id']})")
                    inserted += 1
                else:
                    track = BinauralTrack(
                        title=nr['title'],
                        artist=nr['artist'] or None,
                        emotion=nr['emotion'] or None,
                        youtube_id=nr['youtube_id'] or None,
                        tags=nr['tags'] or None,
                        source_file=os.path.relpath(f, BASE_DIR),
                        created_at=datetime.utcnow()
                    )
                    try:
                        db.session.add(track)
                        db.session.commit()
                        inserted += 1
                        print(f"  Inserted: {track.title} (id={track.id})")
                    except Exception as e:
                        db.session.rollback()
                        print(f"  Failed to insert {nr['title']}: {e}")
                        skipped += 1

        print(f"Import finished. Inserted: {inserted}, Skipped: {skipped}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Show what would be inserted without writing to DB')
    args = parser.parse_args()
    main(dry_run=args.dry_run)
