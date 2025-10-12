#!/usr/bin/env python3
"""
Create Database Schema Directly for MindFullHorizon
"""

import os
import sqlite3

def create_database_schema():
    """Create the database schema directly using SQL"""
    db_path = 'instance/mindful_horizon.db'
    
    # Ensure instance directory exists
    os.makedirs('instance', exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255),
                name VARCHAR(100) NOT NULL,
                role VARCHAR(20),
                institution VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_assessment_at DATETIME,
                profile_pic VARCHAR(255),
                google_id VARCHAR(120) UNIQUE
            )
        ''')
        
        # Create blog_posts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                author_id INTEGER NOT NULL,
                category VARCHAR(50) DEFAULT 'general',
                tags TEXT,
                views INTEGER DEFAULT 0,
                is_featured BOOLEAN DEFAULT 0,
                is_published BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (author_id) REFERENCES users (id)
            )
        ''')
        
        # Create blog_likes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blog_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                post_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (post_id) REFERENCES blog_posts (id),
                UNIQUE(user_id, post_id)
            )
        ''')
        
        # Create blog_comments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blog_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                post_id INTEGER NOT NULL,
                parent_id INTEGER,
                content TEXT NOT NULL,
                is_edited BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (post_id) REFERENCES blog_posts (id),
                FOREIGN KEY (parent_id) REFERENCES blog_comments (id)
            )
        ''')
        
        # Create blog_insights table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blog_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL DEFAULT CURRENT_DATE,
                total_posts INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                top_categories TEXT,
                engagement_rate REAL DEFAULT 0.0,
                most_popular_post_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (most_popular_post_id) REFERENCES blog_posts (id)
            )
        ''')
        
        # Create assessments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                assessment_type VARCHAR(50) NOT NULL,
                score INTEGER NOT NULL,
                responses TEXT,
                ai_insights TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create digital_detox_logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS digital_detox_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date DATE NOT NULL,
                screen_time_hours REAL NOT NULL,
                academic_score INTEGER,
                social_interactions VARCHAR(20),
                ai_score VARCHAR(20),
                ai_suggestion TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create rpm_data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rpm_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date DATE NOT NULL,
                heart_rate INTEGER,
                sleep_duration REAL,
                steps INTEGER,
                mood_score INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create gamification table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gamification (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                points INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                badges TEXT DEFAULT '[]',
                last_activity DATE,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create clinical_notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clinical_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                session_date DATETIME NOT NULL,
                transcript TEXT,
                ai_generated_note TEXT,
                provider_notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (provider_id) REFERENCES users (id),
                FOREIGN KEY (patient_id) REFERENCES users (id)
            )
        ''')
        
        # Create institutional_analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS institutional_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution VARCHAR(100) NOT NULL,
                date DATE NOT NULL,
                total_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                avg_wellness_score REAL,
                avg_screen_time REAL,
                high_risk_users INTEGER DEFAULT 0,
                engagement_rate REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create appointments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider_id INTEGER,
                date DATE NOT NULL,
                time VARCHAR(10) NOT NULL,
                appointment_type VARCHAR(50) NOT NULL,
                notes TEXT,
                status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                rejection_reason TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (provider_id) REFERENCES users (id)
            )
        ''')
        
        # Create goals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                category VARCHAR(50) NOT NULL,
                target_value REAL,
                current_value REAL DEFAULT 0.0,
                unit VARCHAR(20),
                status VARCHAR(20) DEFAULT 'active',
                priority VARCHAR(10) DEFAULT 'medium',
                start_date DATE NOT NULL,
                target_date DATE,
                completed_date DATE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create medications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                dosage VARCHAR(50),
                frequency VARCHAR(50),
                time_of_day VARCHAR(50),
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create medication_logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medication_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medication_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                taken_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medication_id) REFERENCES medications (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create breathing_exercise_logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS breathing_exercise_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exercise_name VARCHAR(100) NOT NULL,
                duration_minutes INTEGER NOT NULL,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create yoga_logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS yoga_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_name VARCHAR(100) NOT NULL,
                duration_minutes INTEGER NOT NULL,
                difficulty_level VARCHAR(20) NOT NULL DEFAULT 'Beginner',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create music_therapy_logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS music_therapy_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mood VARCHAR(50) NOT NULL,
                brainwave VARCHAR(20),
                frequency REAL,
                type VARCHAR(20),
                label VARCHAR(255),
                filename VARCHAR(255),
                duration_minutes INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create progress_recommendations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS progress_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recommendations TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create prescriptions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prescriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                medication_name VARCHAR(200) NOT NULL,
                dosage VARCHAR(100) NOT NULL,
                instructions TEXT,
                issue_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                expiry_date DATETIME,
                FOREIGN KEY (provider_id) REFERENCES users (id),
                FOREIGN KEY (patient_id) REFERENCES users (id)
            )
        ''')
        
        # Create binaural_tracks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS binaural_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(300) NOT NULL,
                artist VARCHAR(200),
                emotion VARCHAR(100),
                youtube_id VARCHAR(100),
                tags TEXT,
                source_file VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create mood_logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mood_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mood_score INTEGER NOT NULL,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                recipient_id INTEGER NOT NULL,
                type VARCHAR(50) NOT NULL DEFAULT 'message',
                payload TEXT,
                message TEXT,
                read BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id)
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_role ON users(role)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_institution ON users(institution)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assessment_user_id ON assessments(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_assessment_type ON assessments(assessment_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_detox_user_id ON digital_detox_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_detox_date ON digital_detox_logs(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_appointment_user_id ON appointments(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_appointment_provider_id ON appointments(provider_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_goal_user_id ON goals(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_medication_user_id ON medications(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mood_user_id ON mood_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_music_user_id ON music_therapy_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_recipient_id ON notifications(recipient_id)')
        
        conn.commit()
        conn.close()
        
        print("Database schema created successfully!")
        return True
        
    except Exception as e:
        print(f"Error creating database schema: {e}")
        return False

def check_tables():
    """Check what tables were created"""
    db_path = 'instance/mindful_horizon.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\nCreated {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error checking tables: {e}")
        return False

def main():
    print("Creating MindFullHorizon Database Schema")
    print("=" * 40)
    
    success = create_database_schema()
    
    if success:
        check_tables()
        print("\nDatabase schema creation completed successfully!")
    else:
        print("Failed to create database schema.")

if __name__ == "__main__":
    main()
