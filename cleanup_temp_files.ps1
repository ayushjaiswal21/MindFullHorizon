# Cleanup script for temporary files
$ErrorActionPreference = "SilentlyContinue"

# Remove Python cache files and directories
Remove-Item -Recurse -Force __pycache__
Remove-Item -Recurse -Force *\__pycache__
Remove-Item -Recurse -Force .pytest_cache

# Remove log files (keep the last 3 days)
$cutoffDate = (Get-Date).AddDays(-3)
Get-ChildItem -Path . -Filter *.log | Where-Object { $_.LastWriteTime -lt $cutoffDate } | Remove-Item -Force

# Remove system temporary files
Remove-Item -Force Thumbs.db
Remove-Item -Force .DS_Store
Remove-Item -Force desktop.ini

# Remove empty directories
Get-ChildItem -Directory -Recurse | Where-Object { (Get-ChildItem -Path $_.FullName -Recurse -File).Count -eq 0 } | Remove-Item -Recurse -Force

Write-Host "Cleanup completed. The following files were removed:"
Write-Host "- Python cache files (*.pyc)"
Write-Host "- __pycache__ directories"
Write-Host "- Log files older than 3 days"
Write-Host "- System temporary files"
Write-Host "- Empty directories"
