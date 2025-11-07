from app import app, db
from models import User

with app.app_context():
    # Check if users exist
    patient = User.query.filter_by(email='patient@example.com').first()
    provider = User.query.filter_by(email='provider@example.com').first()
    
    print("Checking demo users in database...")
    print(f"Patient user exists: {bool(patient)}")
    print(f"Provider user exists: {bool(provider)}")
    
    if not patient or not provider:
        print("\nCreating demo users...")
        try:
            # Create patient user
            if not patient:
                patient = User(
                    email='patient@example.com',
                    name='Demo Patient',
                    role='patient',
                    institution='Demo University'
                )
                patient.set_password('password')
                db.session.add(patient)
                print("Created patient user")
            
            # Create provider user
            if not provider:
                provider = User(
                    email='provider@example.com',
                    name='Demo Provider',
                    role='provider',
                    institution='Demo University'
                )
                provider.set_password('password')
                db.session.add(provider)
                print("Created provider user")
            
            db.session.commit()
            print("Successfully created demo users!")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating users: {str(e)}")
    else:
        print("\nDemo users already exist in the database.")
