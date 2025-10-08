#!/usr/bin/env python3
"""
Debug script to check appointment visibility issues
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, Appointment
from sqlalchemy import or_, and_

def debug_appointments():
    with app.app_context():
        print("=== DEBUGGING APPOINTMENT VISIBILITY ===\n")
        
        # Get all users
        patients = User.query.filter_by(role='patient').all()
        providers = User.query.filter_by(role='provider').all()
        
        print(f"Total Patients: {len(patients)}")
        print(f"Total Providers: {len(providers)}")
        print()
        
        # Show patient institutions
        print("PATIENT INSTITUTIONS:")
        for patient in patients:
            print(f"  - {patient.name} ({patient.email}): '{patient.institution}'")
        print()
        
        # Show provider institutions
        print("PROVIDER INSTITUTIONS:")
        for provider in providers:
            print(f"  - {provider.name} ({provider.email}): '{provider.institution}'")
        print()
        
        # Get all appointments
        appointments = Appointment.query.all()
        print(f"Total Appointments: {len(appointments)}")
        print()
        
        print("ALL APPOINTMENTS:")
        for appt in appointments:
            patient = User.query.get(appt.user_id)
            provider = User.query.get(appt.provider_id) if appt.provider_id else None
            print(f"  - ID: {appt.id}")
            print(f"    Patient: {patient.name if patient else 'Unknown'} ({patient.institution if patient else 'N/A'})")
            print(f"    Provider: {provider.name if provider else 'Unassigned'} ({provider.institution if provider else 'N/A'})")
            print(f"    Date: {appt.date}, Time: {appt.time}")
            print(f"    Status: {appt.status}")
            print(f"    Type: {appt.appointment_type}")
            print()
        
        # Test provider query for each provider
        print("PROVIDER APPOINTMENT VISIBILITY TEST:")
        for provider in providers:
            print(f"\nProvider: {provider.name} (Institution: {provider.institution})")
            
            # Get same institution patients
            same_institution_users = User.query.filter_by(role='patient', institution=provider.institution).with_entities(User.id).all()
            same_institution_user_ids = [user.id for user in same_institution_users]
            print(f"  Same institution patient IDs: {same_institution_user_ids}")
            
            # Run the query
            query = Appointment.query.filter(
                or_(
                    Appointment.provider_id == provider.id,
                    and_(
                        Appointment.provider_id.is_(None),
                        Appointment.user_id.in_(same_institution_user_ids)
                    )
                )
            )
            
            visible_appointments = query.all()
            print(f"  Visible appointments: {len(visible_appointments)}")
            for appt in visible_appointments:
                patient = User.query.get(appt.user_id)
                print(f"    - ID {appt.id}: {patient.name if patient else 'Unknown'} on {appt.date} at {appt.time} (Status: {appt.status})")

if __name__ == "__main__":
    debug_appointments()
