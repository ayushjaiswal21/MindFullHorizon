from app import app, db, User, Assessment, DigitalDetoxLog, RPMData, Gamification, ClinicalNote, InstitutionalAnalytics, Appointment, Goal
import os

# Remove existing database
if os.path.exists('mindful_horizon.db'):
    os.remove('mindful_horizon.db')

# Create all tables
with app.app_context():
    db.create_all()
    print("Database recreated successfully!")
