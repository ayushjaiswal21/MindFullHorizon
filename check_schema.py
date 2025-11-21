#!/usr/bin/env python3
"""Check database schema and add missing column"""

from app import app, db
from models import Assessment

def check_and_fix_schema():
    with app.app_context():
        # Check if contextual_responses column exists
        inspector = db.inspect(db.engine)
        columns = inspector.get_columns('assessments')
        column_names = [col['name'] for col in columns]
        
        print("Current columns in assessments table:", column_names)
        
        if 'contextual_responses' not in column_names:
            print("Adding missing contextual_responses column...")
            # Add the column using raw SQL
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE assessments ADD COLUMN contextual_responses TEXT"))
                conn.commit()
            print("Column added successfully!")
        else:
            print("contextual_responses column already exists.")

if __name__ == '__main__':
    check_and_fix_schema()
