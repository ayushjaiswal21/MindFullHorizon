"""Builders for inventory and dispensing tests. They write rows directly with the models (no service under test)."""
from datetime import timedelta

from extensions import db
from models import InventoryBatch, InventoryTransaction, Medicine, Prescription, PrescriptionItem
from utils.rx_numbers import new_number
from utils.timeutil import ist_today, utcnow

INST = 'test university'  # institution key of the make_user default 'Test University'


def med(app, name='Testamol', strength='10 mg', form='tablet', tpg_list='O', schedule='none', **kw):
    with app.app_context():
        m = Medicine(generic_name=name, generic_key=name.lower(), brand_name=kw.pop('brand_name', ''), strength=strength,
                     form=form, tpg_list=tpg_list, schedule=schedule, is_controlled=schedule in ('X', 'NDPS', 'H1'),
                     list_verified_at=utcnow(), **kw)
        db.session.add(m)
        db.session.commit()
        return m.id


def batch(app, medicine_id, qty, batch_no='B1', days=100, inst=INST, status='active'):
    """Batch with `qty` on hand and the matching opening ledger row, so reconcile() is clean."""
    with app.app_context():
        b = InventoryBatch(institution_key=inst, medicine_id=medicine_id, batch_no=batch_no,
                           expiry_date=ist_today() + timedelta(days=days), quantity_on_hand=qty, status=status)
        db.session.add(b)
        db.session.flush()
        db.session.add(InventoryTransaction(batch_id=b.id, delta=qty, kind='receive', reason_code='opening_stock',
                                            idempotency_key=f'seed:{b.id}:{batch_no}', created_at=utcnow()))
        db.session.commit()
        return b.id


def rx(app, patient_id, doctor_id, lines, inst=INST, status='issued', days_valid=10, requested=True,
       patient_name='Asha Sharma'):
    """Issued prescription. `lines` is a list of (medicine_id, quantity). Returns the prescription id."""
    with app.app_context():
        now = utcnow()
        p = Prescription(provider_id=doctor_id, patient_id=patient_id, number=new_number(), status=status,
                         institution_key=inst, institution_name='Test University', doctor_name='Dr Demo',
                         doctor_reg_no='REG1', patient_name=patient_name, issue_date=now,
                         expiry_date=now + timedelta(days=days_valid),
                         dispense_requested_at=now if requested else None, diagnosis='F41.1')
        db.session.add(p)
        db.session.flush()
        for n, (mid, qty) in enumerate(lines, start=1):
            db.session.add(PrescriptionItem(prescription_id=p.id, line_no=n, medicine_id=mid, medicine_label=f'ITEM{mid}',
                                            dose_text='1 tablet', frequency='daily', duration_days=5, quantity=qty))
        db.session.commit()
        return p.id


def on_hand(app, batch_id):
    with app.app_context():
        return db.session.get(InventoryBatch, batch_id).quantity_on_hand


def client_for(app, user_id):
    """A fresh test client logged in as `user_id` (same session keys as the login route)."""
    from models import User
    c = app.test_client()
    with app.app_context():
        u = db.session.get(User, user_id)
        data = dict(user_email=u.email, user_role=u.role, user_name=u.name, user_institution=u.institution)
    with c.session_transaction() as s:
        s['user_id'] = user_id
        s.update(data)
    return c
