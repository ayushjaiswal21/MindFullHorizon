"""Demo clinical data for scripts/seed_demo.py: medicines, stock, a consult, consent and one prescription.

Everything here is FICTIONAL and marked DEMO (`Medicine.is_demo = True`, names end with "(DEMO)"). Never run in
production. Idempotent: running twice adds nothing. Called inside an app context by seed_demo.seed().
"""
from datetime import timedelta

DEMO_INSTITUTION = 'Demo University'
INSTITUTION_KEY = 'demo university'

# generic name, strength, form, TPG list, schedule, controlled, therapeutic class, batches (days to expiry, quantity)
MEDICINES = [
    ('Democillin (DEMO)', '10 mg', 'tablet', 'O', 'none', False, 'demo-class-a', [(400, 200), (35, 40)]),
    ('Placebamine (DEMO)', '20 mg', 'tablet', 'A', 'H', False, 'demo-class-b', [(300, 120)]),
    ('Calmexol (DEMO)', '5 mg', 'tablet', 'A', 'none', False, 'demo-class-b', [(-10, 25), (200, 60)]),
    ('Sleepoxin (DEMO)', '25 mg', 'tablet', 'B', 'H', False, 'demo-class-c', [(250, 80)]),
    ('Moodamol (DEMO)', '50 mg', 'capsule', 'B', 'H', False, None, []),
    ('Noverlist (DEMO)', '0.5 mg', 'tablet', 'C', 'H', False, None, []),
    ('Controlex (DEMO)', '1 mg', 'tablet', 'C', 'H1', True, None, []),
    ('Demovit (DEMO)', '100 mg', 'syrup', 'O', 'none', False, None, [(500, 30)]),
]


def seed_clinical(db, users, utcnow, ist_today):
    """`users` maps the keys patient, counsellor, doctor, admin, admin2 to User rows. Returns a list of message lines."""
    from models import (Appointment, ConsentRecord, InventoryBatch, InventoryTransaction, Medicine,
                        PrescriberProfile, Prescription, PrescriptionItem, ProviderPatient)
    from services.config import erx_consent_version
    from utils.rx_numbers import new_number
    out = []
    now = utcnow()
    admin, admin2, doctor, patient = users['admin'], users['admin2'], users['doctor'], users['patient']

    # Doctor profile: verified, clearly marked as not a real registration.
    if not PrescriberProfile.query.filter_by(user_id=doctor.id).first():
        db.session.add(PrescriberProfile(
            user_id=doctor.id, registration_number='DEMO0001', council='DEMO COUNCIL', council_key='demo council',
            registered_since=2010, specialisation='General medicine (DEMO)', status='verified', verified_at=now,
            verified_by=admin.id, review_due_at=now + timedelta(days=365), status_changed_at=now,
            notes='DEMO ONLY, not a real registration'))
        out.append('Demo doctor profile created (verified, DEMO0001).')

    # Assignments: the patient is linked to both staff members, as a booking would do.
    for staff in (users['counsellor'], doctor):
        if not ProviderPatient.query.filter_by(provider_id=staff.id, patient_id=patient.id).first():
            db.session.add(ProviderPatient(provider_id=staff.id, patient_id=patient.id, source='manual'))

    # Consult in progress and consent, so the doctor can try prescribing at once.
    if not Appointment.query.filter_by(user_id=patient.id, client_request_id='demo-seed-consult').first():
        db.session.add(Appointment(user_id=patient.id, provider_id=doctor.id, date=ist_today(), time='10:00',
                                   appointment_type='consultation', status='accepted', modality='video',
                                   consult_started_at=now, client_request_id='demo-seed-consult'))
        out.append('Demo video consult started between the demo patient and the demo doctor.')
    version = erx_consent_version()
    if not ConsentRecord.query.filter_by(user_id=patient.id, kind='eprescription', version=version).first():
        db.session.add(ConsentRecord(user_id=patient.id, kind='eprescription', version=version, accepted_at=now))

    # Medicines: created by one demo admin, classification confirmed by the other (four-eyes).
    meds = {}
    for generic, strength, form, tpg, schedule, controlled, klass, batches in MEDICINES:
        med = Medicine.query.filter_by(generic_key=generic.lower(), brand_name='', strength=strength, form=form).first()
        if not med:
            med = Medicine(generic_name=generic, generic_key=generic.lower(), brand_name='', strength=strength, form=form,
                           route='oral', tpg_list=tpg, schedule=schedule, is_controlled=controlled,
                           therapeutic_class=klass, active=True, is_demo=True, list_verified_at=now,
                           list_verified_by=admin2.id, created_by=admin.id, updated_by=admin.id)
            db.session.add(med)
            out.append(f'Demo medicine: {generic} {strength} {form}, list {tpg}.')
        db.session.flush()
        meds[generic] = med
        for n, (days, qty) in enumerate(batches, 1):
            expiry = ist_today() + timedelta(days=days)
            batch_no = f'DEMO-{med.id}-{n}'
            if InventoryBatch.query.filter_by(institution_key=INSTITUTION_KEY, medicine_id=med.id, batch_no=batch_no).first():
                continue
            batch = InventoryBatch(institution_key=INSTITUTION_KEY, medicine_id=med.id, batch_no=batch_no,
                                   expiry_date=expiry, quantity_on_hand=qty, supplier='Demo Supplier', status='active')
            db.session.add(batch)
            db.session.flush()
            db.session.add(InventoryTransaction(batch_id=batch.id, delta=qty, kind='receive', reason_code='opening_stock',
                                                actor_id=users['admin'].id, idempotency_key=f'demo-seed:batch:{batch.id}'))

    # One issued sample prescription, built from snapshots like a real issue.
    if not Prescription.query.filter_by(provider_id=doctor.id, client_request_id='demo-seed-rx').first():
        issued = now
        rx = Prescription(
            provider_id=doctor.id, patient_id=patient.id, status='issued', number=new_number(now),
            institution_key=INSTITUTION_KEY, institution_name=DEMO_INSTITUTION, doctor_name=doctor.name,
            doctor_reg_no='DEMO0001', doctor_council='DEMO COUNCIL', doctor_specialisation='General medicine (DEMO)',
            patient_name=patient.name, tpg_context='first', diagnosis='Demo diagnosis (DEMO)',
            allergies_status='none_reported', current_meds_status='none_reported', consent_version=version,
            issue_date=issued, expiry_date=issued + timedelta(days=14), expiry_days=14,
            client_request_id='demo-seed-rx', issue_request_id='demo-seed-rx')
        db.session.add(rx)
        db.session.flush()
        for line, key in enumerate(('Democillin (DEMO)', 'Calmexol (DEMO)'), 1):
            med = meds[key]
            db.session.add(PrescriptionItem(
                prescription_id=rx.id, line_no=line, medicine_id=med.id, tpg_list=med.tpg_list,
                medicine_label=f'{med.generic_name.upper()} {med.strength} {med.form}', dose_text='1 tablet',
                frequency='once daily after food', duration_days=7, quantity=7, instructions='Demo only'))
        out.append(f'Demo prescription issued: {rx.number}.')
    return out
