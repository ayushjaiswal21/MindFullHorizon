#!/usr/bin/env python3
"""
Create demo users immediately
"""
import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime

def create_demo_users():
    db_path = 'instance/mindful_horizon.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Demo users
    users = [
        ('patient@example.com', 'password', 'Demo Patient', 'patient', 'Demo University'),
        ('provider@example.com', 'password', 'Demo Provider', 'provider', 'Demo University')
    ]
    
    for email, password, name, role, institution in users:
        # Delete if exists
        cursor.execute("DELETE FROM users WHERE email = ?", (email,))
        cursor.execute("DELETE FROM gamification WHERE user_id IN (SELECT id FROM users WHERE email = ?)", (email,))
        
        # Create user
        password_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (email, password_hash, name, role, institution, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, password_hash, name, role, institution, datetime.now()))
        
        user_id = cursor.lastrowid
        
        # Add gamification for patient
        if role == 'patient':
            cursor.execute("""
                INSERT INTO gamification (user_id, points, streak, badges, last_activity)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, 50, 3, '["Welcome"]', datetime.now().date()))
        
        print(f"✅ Created: {email}")
    
    conn.commit()
    conn.close()
    print("🎉 Demo users ready!")

if __name__ == "__main__":
    create_demo_users()