#!/usr/bin/env python3
"""
Simple Database Backup Script for MindFullHorizon
Creates a backup of the SQLite database file.
"""

import os
import shutil
from datetime import datetime

def backup_database():
    """Create a backup of the SQLite database"""
    # Look for common SQLite database files
    possible_db_files = [
        'instance/mindful_horizon.db',
        'mindful_horizon.db',
        'app.db',
        'instance/app.db',
        'database.db',
        'instance/database.db'
    ]
    
    db_file = None
    for file_path in possible_db_files:
        if os.path.exists(file_path):
            db_file = file_path
            break
    
    if not db_file:
        print("No SQLite database file found in common locations:")
        for path in possible_db_files:
            print(f"  - {path}")
        return False
    
    # Create backup directory
    backup_dir = 'database_backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'mindful_horizon_backup_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        shutil.copy2(db_file, backup_path)
        print(f"Database backup created: {backup_path}")
        print(f"Original database: {db_file}")
        return True
    except Exception as e:
        print(f"Error creating backup: {str(e)}")
        return False

if __name__ == "__main__":
    print("Creating database backup...")
    success = backup_database()
    if success:
        print("Backup completed successfully!")
    else:
        print("Backup failed!")
