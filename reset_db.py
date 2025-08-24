import os
from app import app, db
from models import User, Assessment, DigitalDetoxLog, RPMData, Gamification, ClinicalNote, InstitutionalAnalytics, Appointment, Goal
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import json

def reset_database():
    # Delete existing database
    if os.path.exists('instance/mindful_horizon.db'):
        os.remove('instance/mindful_horizon.db')
    
    # Create all tables
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create a test user
        password_hash = generate_password_hash('password')
        user = User(
            email='test@example.com',
            name='Test User',
            password=password_hash,
            role='patient'
        )
        db.session.add(user)
        db.session.commit()
        
        # Create a sample assessment
        assessment = Assessment(
            user_id=user.id,
            assessment_type='PHQ-9',
            score=5,
            responses=json.dumps({"q1": 1, "q2": 1, "q3": 1, "q4": 1, "q5": 1}),
            ai_insights=json.dumps({
                'summary': 'Mild symptoms of depression',
                'recommendations': ['Practice mindfulness', 'Get regular exercise'],
                'resources': ['Mindfulness app', 'Exercise guide']
            }),
            created_at=datetime.utcnow()
        )
        db.session.add(assessment)
        
        # Commit all changes
        db.session.commit()
        
        print("Database reset successfully!")
        print(f"Created user: test@example.com / password")
        print(f"User ID: {user.id}")

if __name__ == '__main__':
    reset_database()
