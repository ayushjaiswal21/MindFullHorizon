#!/bin/bash
# This script moves old AI-related files to an archive directory.

# Create the archive directory if it doesn't exist
mkdir -p archive

# Move the old files
if [ -f "ai_service.py.backup" ]; then
    echo "Archiving ai_service.py.backup"
    git mv ai_service.py.backup archive/
fi

echo "Cleanup complete. Old files have been moved to the archive/ directory."
