#!/bin/bash
# This script will delete the archive directory after confirmation
# Run with: bash delete_confirm.sh

ARCHIVE_DIR="$(dirname "$0")/archive"

echo "WARNING: This will permanently delete the archive directory and all its contents!"
echo "Contents of $ARCHIVE_DIR:"
find "$ARCHIVE_DIR" -type f -o -type d | sort

echo -n "
Type 'YES' to confirm deletion: "
read -r confirm

if [ "$confirm" = "YES" ]; then
    echo "Deleting $ARCHIVE_DIR..."
    rm -rf "$ARCHIVE_DIR"
    echo "Archive deleted."
else
    echo "Deletion cancelled."
fi
