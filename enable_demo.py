#!/usr/bin/env python3
"""
Enable demo users for MindFull Horizon
"""

import sqlite3
import sys
import os

# Add the current directory to Python path to import werkzeug
sys.path.insert(0, os.getcwd())

try:
    from werkzeug.security import generate_password_hash
    from datetime import datetime
    
    def enable_demo_users():
        """Enable demo users in the database"""
        db_path = 'instance/mindful_horizon.db'
        
        if not os.path.exists(db_path):
            print("❌ Database not found. Please run create_schema_direct.py first.")
            return False
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Demo users
            demo_users = [
                ('patient@example.com', 'password', 'Demo Patient', 'patient', 'Demo University'),
                ('provider@example.com', 'password', 'Demo Provider', 'provider', 'Demo University')
            ]
            
            for email, password, name, role, institution in demo_users:
                # Check if user exists
                cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                existing = cursor.fetchone()
                
                password_hash = generate_password_hash(password)
                
                if existing:
                    # Update existing user
                    cursor.execute("""
                        UPDATE users 
                        SET password_hash = ?, name = ?, role = ?, institution = ?
                        WHERE email = ?
                    """, (password_hash, name, role, institution, email))
                    print(f"✅ Updated: {email}")
                else:
                    # Create new user
                    cursor.execute("""
                        INSERT INTO users (email, password_hash, name, role, institution, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (email, password_hash, name, role, institution, datetime.now()))
                    
                    user_id = cursor.lastrowid
                    
                    # Add gamification for patient
                    if role == 'patient':
                        cursor.execute("""
                            INSERT OR REPLACE INTO gamification (user_id, points, streak, badges, last_activity)
                            VALUES (?, ?, ?, ?, ?)
                        """, (user_id, 50, 3, '["Welcome"]', datetime.now().date()))
                    
                    print(f"✅ Created: {email}")
            
            conn.commit()
            conn.close()
            
            print("\n🎉 Demo users enabled successfully!")
            print("=" * 50)
            print("Demo Credentials:")
            print("Student: patient@example.com / password")
            print("Provider: provider@example.com / password")
            print("=" * 50)
            print("🚀 Login at: http://localhost:5000/login")
            
            return True
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False
    
    if __name__ == "__main__":
        print("🧠 Enabling Demo Users for MindFull Horizon")
        print("=" * 45)
        enable_demo_users()

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please make sure you're in the correct directory with all dependencies installed.")