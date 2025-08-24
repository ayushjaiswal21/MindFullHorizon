#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Initialize the database unless explicitly skipped (e.g., on Render with Postgres)
if [ "${SKIP_DB_INIT}" != "true" ]; then
  echo "Running init_database() (override with SKIP_DB_INIT=true)"
  python -c "from app import init_database; init_database()"
else
  echo "Skipping database initialization (SKIP_DB_INIT=true)"
fi
