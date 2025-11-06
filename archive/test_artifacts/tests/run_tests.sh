#!/bin/bash

# Exit on first error
set -e

# Install dependencies globally
echo "--- Installing dependencies globally (no virtual environment) ---"
pip install -r requirements.txt
pip install pytest

# Create a default .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "DATABASE_URL=sqlite:///instance/dev.db" > .env
    echo "GEMINI_API_KEY=" >> .env
fi

# Run tests on a single port
echo "--- Running tests on single port ---"
pytest -q --maxfail=1 --disable-warnings

# Run tests on multiple ports with separate databases
echo "--- Running tests on multiple ports ---"
DATABASE_URL=sqlite:///instance/dev_5000.db FLASK_RUN_PORT=5000 pytest -q
DATABASE_URL=sqlite:///instance/dev_5001.db FLASK_RUN_PORT=5001 pytest -q