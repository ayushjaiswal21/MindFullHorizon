# Script to archive cleanup scripts and test files
$archiveDir = "archive/removed_$(Get-Date -Format 'yyyyMMdd-HHmm')"

# Create archive directory
New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null

# Files to archive
$filesToArchive = @(
    "archive_cleanup.py",
    "cleanup.sh",
    "cleanup_temp_files.ps1",
    "simple_cleanup.py",
    "remove_unused_files.ps1",
    "tests"
)

# Move files to archive
foreach ($file in $filesToArchive) {
    if (Test-Path $file) {
        $dest = Join-Path $archiveDir (Split-Path $file -Leaf)
        Move-Item -Path $file -Destination $dest -Force
        Write-Host "Moved to archive: $file"
    }
}

# Create a cleanup script for the archive
$cleanupScript = @"
# This script will help you clean up the archive directory
# Run with: bash cleanup_archive.sh

ARCHIVE_DIR="archive"

if [ ! -d "`$ARCHIVE_DIR" ]; then
    echo "No archive directory found."
    exit 0
fi

echo "The following archive directories will be removed:"
find "`$ARCHIVE_DIR" -maxdepth 1 -type d -name "removed_*" | sort

echo -n "\nDo you want to remove these directories? (y/N) "
read -r confirm

if [[ "`$confirm" =~ ^[Yy]$ ]]; then
    echo "Removing archive directories..."
    find "`$ARCHIVE_DIR" -maxdepth 1 -type d -name "removed_*" -exec rm -rf {} \;
    echo "Cleanup complete."
else
    echo "Cleanup cancelled."
fi
"@

# Save the cleanup script
$cleanupScriptPath = "cleanup_archive.sh"
[System.IO.File]::WriteAllText((Join-Path $PWD $cleanupScriptPath), $cleanupScript)

Write-Host "`nCleanup complete. Removed files have been moved to: $archiveDir"
Write-Host "You can use 'bash cleanup_archive.sh' to review and clean up the archive directories."
