# This script will help you clean up the archive directory
# Run with: bash cleanup_archive.sh

ARCHIVE_DIR="archive"

if [ ! -d "$ARCHIVE_DIR" ]; then
    echo "No archive directory found."
    exit 0
fi

echo "The following archive directories will be removed:"
find "$ARCHIVE_DIR" -maxdepth 1 -type d -name "removed_*" | sort

echo -n "\nDo you want to remove these directories? (y/N) "
read -r confirm

if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Removing archive directories..."
    find "$ARCHIVE_DIR" -maxdepth 1 -type d -name "removed_*" -exec rm -rf {} \;
    echo "Cleanup complete."
else
    echo "Cleanup cancelled."
fi