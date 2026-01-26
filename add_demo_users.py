#!/usr/bin/env python3
"""
Add demo users to MindFull Horizon database
"""

import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime

def add_demo_users():
    """Add demo users with simple credentials"""
    db_path = 'instance/mindful_horizon.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Demo users with simple passwords
        demo_users = [
            {
                'email': 'patient@example.com',
                'password': 'password',
                'name': 'Demo Patient',
                'role': 'patient',
                'institution': 'Demo University'
            },
            {
                'email': 'provider@example.com', 
                'password': 'password',
                'name': 'Demo Provider',
                'role': 'provider',
                'institution': 'Demo University'
            }
        ]
        
        for user_data in demo_users:
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE email = ?", (user_data['email'],))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # Update existing user's password
                password_hash = generate_password_hash(user_data['password'])
                cursor.execute("""
                    UPDATE users 
                    SET password_hash = ?, name = ?, role = ?, institution = ?
                    WHERE email = ?
                """, (
                    password_hash,
                    user_data['name'],
                    user_data['role'],
                    user_data['institution'],
                    user_data['email']
                ))
                print(f"✅ Updated user: {user_data['email']}")
            else:
                # Create new user
                password_hash = generate_password_hash(user_data['password'])
                cursor.execute("""
                    INSERT INTO users (email, password_hash, name, role, institution, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_data['email'],
                    password_hash,
                    user_data['name'],
                    user_data['role'],
                    user_data['institution'],
                    datetime.utcnow()
                ))
                
                user_id = cursor.lastrowid
                
                # Create gamification record for patients
                if user_data['role'] == 'patient':
                    cursor.execute("""
                        INSERT INTO gamification (user_id, points, streak, badges, last_activity)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, 50, 3, '["Welcome", "First Assessment"]', datetime.utcnow().date()))
                
                print(f"✅ Created user: {user_data['email']}")
        
        conn.commit()
        conn.close()
        
        print("\n🎉 Demo users are ready!")
        print("=" * 40)
        print("Demo Credentials (for testing):")
        print("Student: patient@example.com / password")
        print("Provider: provider@example.com / password")
        print("=" * 40)
        print("\n🚀 You can now login at: http://localhost:5000/login")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧠 Adding Demo Users to MindFull Horizon")
    add_demo_users()