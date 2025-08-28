#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Initialize the database unless explicitly skipped
if [ "${SKIP_DB_INIT}" != "true" ]; then
  echo "Running database initialization..."
  python -c "from app import app, init_database; init_database(app)"
else
  echo "Skipping database initialization (SKIP_DB_INIT=true)"
fi
