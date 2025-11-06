Clone instructions for binaural-beats-dataset

This project can optionally enrich the Mood Music / Mood -> binaural-beats mapping by using the public dataset:

https://github.com/neelkamath/binaural-beats-dataset.git

Steps to install locally:

1. From the repository root, run:

   git clone https://github.com/neelkamath/binaural-beats-dataset.git data/binaural-beats-dataset

2. The app looks for common files like `tracks.csv`, `dataset.csv`, `tracks.json`, or `data.json` inside `data/binaural-beats-dataset/`.

3. After cloning, restart the Flask server. The `/api/mood-music` endpoint will attempt to parse the dataset and return curated `videos` (when `youtube_id` is present) or enhance the search `query`.

Notes:
- The integration is best-effort and will gracefully fall back to the built-in static mapping if the dataset isn't present or is malformed.
- Ensure you have permission to use any YouTube IDs or tracks for your deployment and comply with licenses.

Importing into the application's database
---------------------------------------

If you'd like to persist the dataset into the application's database, there's a helper import script.

From the repository root run (dry-run first):

```powershell
python -m scripts.import_binaural_dataset --dry-run
```

If the dry-run output looks good, run without `--dry-run` to insert records:

```powershell
python -m scripts.import_binaural_dataset
```

The script will avoid inserting duplicates by matching `youtube_id` or `title`+`artist`.

After importing, the `/api/mood-music` endpoint will prefer DB-backed tracks when building mood -> videos mappings.