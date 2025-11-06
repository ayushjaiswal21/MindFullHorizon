import os
import shutil
import json
from datetime import datetime
from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).parent
ARCHIVE_DIR = REPO_ROOT / 'archive'
LOG_FILE = REPO_ROOT / 'cleanup.log'
DELETE_CONFIRM_SCRIPT = REPO_ROOT / 'delete_confirm.sh'

# Define patterns to match files for archiving
PATTERNS = {
    'test_artifacts': ['tests/**/*', 'testing/**/*', '**/__pycache__/**', '**/*.pyc'],
    'backups': ['**/*_backup.*', '**/*.backup', '**/*~', '**/*.old', '**/*.bak'],
    'large_markdowns': ['**/*REPORT*.md', '**/*_ANALYSIS.md', '**/README_*', '**/README_BACKUP.md'],
    'dev_dbs': ['**/dev.db', '**/test_*.db', '**/test_*.sqlite'],
    'deployment_dups': ['**/render.yaml.bak', '**/vercel.json.old', '**/Procfile.backup'],
    'logs_and_temp': ['**/*.log', '**/static/tmp/**', '**/tmp/**']
}

# Files to never move
NEVER_MOVE = {
    'README.md', 'LICENSE', 'setup.py', 'pyproject.toml', 'requirements.txt', 'Dockerfile',
    'render.yaml', 'vercel.json', 'Procfile', '.github', '.gitignore'
}

def get_file_size(path: Path) -> str:
    """Get human-readable file size."""
    size = path.stat().st_size
    for unit in ['B', 'K', 'M', 'G']:
        if size < 1024 or unit == 'G':
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}B"

def is_gitignored(path: Path) -> bool:
    """Check if a file is gitignored."""
    try:
        result = subprocess.run(
            ['git', 'check-ignore', str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def find_files_to_archive() -> list[dict]:
    """Find files matching our patterns that can be safely archived."""
    candidates = []
    
    for category, patterns in PATTERNS.items():
        for pattern in patterns:
            for path in REPO_ROOT.glob(pattern):
                # Skip if in archive dir or matches NEVER_MOVE
                if path.is_relative_to(ARCHIVE_DIR) or path.name in NEVER_MOVE:
                    continue
                    
                # Skip gitignored files
                if is_gitignored(path):
                    continue
                    
                # Skip if already in our candidates
                if any(c['path'] == str(path) for c in candidates):
                    continue
                
                # Determine risk level
                risk = 'low'
                if any(part.startswith('.') and part not in ('.git', '.github') for part in path.parts):
                    risk = 'medium'
                if any(part in str(path) for part in ['prod', 'production', 'config']):
                    risk = 'high'
                
                candidates.append({
                    'path': str(path),
                    'category': category,
                    'size': get_file_size(path) if path.is_file() else 'dir',
                    'risk': risk
                })
    
    return candidates

def create_archive_structure():
    """Create archive directory structure."""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    
    # Create category subdirectories
    for category in PATTERNS.keys():
        (ARCHIVE_DIR / category).mkdir(exist_ok=True)

def move_files(candidates: list[dict], dry_run: bool = True) -> list[dict]:
    """Move files to archive directory."""
    moved = []
    
    for item in candidates:
        src = Path(item['path'])
        rel_path = src.relative_to(REPO_ROOT)
        dest = ARCHIVE_DIR / item['category'] / rel_path
        
        # Create parent directories in destination
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if dry_run:
                print(f"Would move: {src} -> {dest}")
            else:
                # Use git mv if file is tracked by git
                git_status = subprocess.run(
                    ['git', 'ls-files', '--error-unmatch', str(src)],
                    cwd=REPO_ROOT,
                    capture_output=True
                )
                
                if git_status.returncode == 0:  # File is tracked by git
                    subprocess.run(
                        ['git', 'mv', str(src), str(dest)],
                        cwd=REPO_ROOT,
                        check=True
                    )
                else:
                    shutil.move(str(src), str(dest))
                
                print(f"Moved: {src} -> {dest}")
            
            moved.append({
                'path': str(src),
                'archive_path': str(dest),
                'size': item['size'],
                'reason': item['category'],
                'risk': item['risk']
            })
            
        except Exception as e:
            print(f"Error moving {src}: {str(e)}")
            if 'errors' not in item:
                item['errors'] = []
            item['errors'].append(str(e))
    
    return moved

def create_delete_confirm_script():
    """Create a script to safely delete the archive."""
    content = """#!/bin/bash
# This script will delete the archive directory after confirmation
# Run with: bash delete_confirm.sh

ARCHIVE_DIR="$(dirname "$0")/archive"

echo "WARNING: This will permanently delete the archive directory and all its contents!"
echo "Contents of $ARCHIVE_DIR:"
find "$ARCHIVE_DIR" -type f -o -type d | sort

echo -n "\nType 'YES' to confirm deletion: "
read -r confirm

if [ "$confirm" = "YES" ]; then
    echo "Deleting $ARCHIVE_DIR..."
    rm -rf "$ARCHIVE_DIR"
    echo "Archive deleted."
else
    echo "Deletion cancelled."
fi
"""
    DELETE_CONFIRM_SCRIPT.write_text(content)
    DELETE_CONFIRM_SCRIPT.chmod(0o755)  # Make it executable

def main():
    # Check if we should execute or dry run
    mode = os.environ.get('AUTO_CLEANUP_MODE', 'DRY_RUN')
    dry_run = mode != 'EXECUTE'
    
    print(f"Running in {mode} mode")
    
    # Create log file
    log = []
    
    # Create archive structure
    create_archive_structure()
    
    # Find files to archive
    log.append("Finding files to archive...")
    candidates = find_files_to_archive()
    
    if not candidates:
        log.append("No files to archive found.")
        print("No files to archive found.")
        return
    
    # Print plan
    log.append(f"Found {len(candidates)} candidate files:")
    for i, item in enumerate(candidates, 1):
        log_entry = f"{i}. {item['path']} ({item['size']}) — {item['category']} — Risk: {item['risk']}"
        log.append(log_entry)
        print(log_entry)
    
    # Move files
    log.append("\nMoving files...")
    moved = move_files(candidates, dry_run=dry_run)
    
    # Create delete confirmation script
    create_delete_confirm_script()
    log.append(f"\nCreated delete confirmation script: {DELETE_CONFIRM_SCRIPT}")
    
    # If in execute mode, commit changes
    commit_sha = 'none'
    if not dry_run and moved:
        try:
            # Add delete_confirm.sh to git
            subprocess.run(
                ['git', 'add', str(DELETE_CONFIRM_SCRIPT)],
                cwd=REPO_ROOT,
                check=True
            )
            
            # Commit changes
            commit_msg = f"chore: archive clutter - auto cleanup {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            result = subprocess.run(
                ['git', 'commit', '-m', commit_msg],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                commit_sha = subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=REPO_ROOT,
                    text=True
                ).strip()
                log.append(f"Committed changes: {commit_sha}")
            else:
                log.append(f"Error committing changes: {result.stderr}")
        except Exception as e:
            log.append(f"Error during git operations: {str(e)}")
    
    # Get git status
    try:
        git_status = subprocess.check_output(
            ['git', 'status', '--porcelain'],
            cwd=REPO_ROOT,
            text=True
        ).splitlines()[:40]
    except Exception as e:
        git_status = [f"Error getting git status: {str(e)}"]
    
    # Get archive preview
    try:
        archive_preview = []
        for root, dirs, files in os.walk(ARCHIVE_DIR):
            level = root.replace(str(ARCHIVE_DIR), '').count(os.sep)
            indent = ' ' * 4 * level
            archive_preview.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files[:10]:  # Limit to first 10 files per directory
                archive_preview.append(f"{subindent}{f}")
            if len(files) > 10:
                archive_preview.append(f"{subindent}... and {len(files) - 10} more files")
        archive_preview = archive_preview[:50]  # Limit to 50 lines total
    except Exception as e:
        archive_preview = [f"Error getting archive preview: {str(e)}"]
    
    # Prepare summary
    summary = {
        'mode': mode,
        'branch': subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=REPO_ROOT,
            text=True
        ).strip(),
        'moved': moved,
        'moved_count': len(moved),
        'commit': commit_sha,
        'archive_preview': archive_preview,
        'git_status': git_status,
        'errors': [item['errors'] for item in candidates if 'errors' in item]
    }
    
    # Write log
    LOG_FILE.write_text('\n'.join(log) + '\n\n' + json.dumps(summary, indent=2))
    
    # Print summary
    print("\n" + "="*80)
    print(f"Cleanup complete. Moved {len(moved)} files to archive.")
    print(f"Log file: {LOG_FILE}")
    print("\nSummary:" + json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
