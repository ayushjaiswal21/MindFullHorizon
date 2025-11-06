# Script to remove unused files and move them to archive first
$archiveDir = "archive/removed_$(Get-Date -Format 'yyyyMMdd-HHmm')"

# Create archive directory
New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null

# List of files to remove
$filesToRemove = @(
    "PATIENT_ROUTES_FIX_REPORT.md",
    "REQUIREMENTS_UPDATE_SUMMARY.md",
    "ROUTE_DUPLICATE_FIX.md",
    "URL_BUILDING_FIX_REPORT.md",
    "migrations/README",
    "data/README.md",
    "cleanup.log",
    "database_cleanup.log"
)

# Move files to archive and remove them
foreach ($file in $filesToRemove) {
    if (Test-Path $file) {
        $destDir = Join-Path $archiveDir (Split-Path $file -Parent)
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        Move-Item -Path $file -Destination $destDir -Force
        Write-Host "Moved to archive: $file"
    }
}

# Remove empty directories
Get-ChildItem -Directory -Recurse | Where-Object { 
    (Get-ChildItem -Path $_.FullName -Recurse -File).Count -eq 0 
} | Remove-Item -Recurse -Force

Write-Host "`nCleanup complete. Removed files have been moved to: $archiveDir"
Write-Host "You can review them and run 'Remove-Item -Recurse -Force $archiveDir' to permanently delete them."
