"""Clinical tables: prescriber profile, prescriptions and items, medicine catalogue, stock and ledger.

Same metadata as models.py (imported at the bottom of that file, so `from models import Medicine` keeps working).
Design: docs/CLINICAL_DESIGN.md sections 2 to 4 and 6. Table and constraint names are exact: tests compare them with
the migrations.
"""
from core.extensions import db
from utils.timeutil import utcnow

__all__ = ["PrescriberProfile", "Medicine", "InventoryBatch", "ReorderRule", "Prescription", "PrescriptionItem",
           "InventoryTransaction"]

_LIVE_PROFILE = "status IN ('pending','verified','suspended')"
_THREE = "('none_reported','listed','unknown')"


class PrescriberProfile(db.Model):
    """A doctor's registration details and the verification decision of an institution admin (design 2.1)."""
    __tablename__ = 'prescriber_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    registration_number = db.Column(db.String(20), nullable=False)
    council = db.Column(db.String(100), nullable=False)
    council_key = db.Column(db.String(100), nullable=False)
    registered_since = db.Column(db.Integer, nullable=False)
    specialisation = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(10), nullable=False, default='pending')
    submitted_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    review_due_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(500), nullable=True)
    status_changed_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    user = db.relationship('User', foreign_keys=[user_id],
                           backref=db.backref('prescriber_profile', uselist=False, passive_deletes=True))

    __table_args__ = (
        db.CheckConstraint("status IN ('pending','verified','rejected','suspended')", name='ck_prescriber_status'),
        db.Index('idx_prescriber_status', 'status'),
        db.Index('uq_prescriber_reg_active', 'registration_number', 'council_key', unique=True,
                 sqlite_where=db.text(_LIVE_PROFILE), postgresql_where=db.text(_LIVE_PROFILE)),
    )


class Medicine(db.Model):
    """Catalogue entry, shared by all institutions. List and schedule are data confirmed by a second admin (design 4.1)."""
    __tablename__ = 'medicines'
    id = db.Column(db.Integer, primary_key=True)
    generic_name = db.Column(db.String(120), nullable=False)
    generic_key = db.Column(db.String(120), nullable=False)
    brand_name = db.Column(db.String(120), nullable=False, default='')
    strength = db.Column(db.String(40), nullable=False)
    form = db.Column(db.String(30), nullable=False)
    route = db.Column(db.String(20), nullable=False, default='oral')
    tpg_list = db.Column(db.String(1), nullable=False, default='C')
    schedule = db.Column(db.String(8), nullable=False, default='none')
    is_controlled = db.Column(db.Boolean, nullable=False, default=False)
    therapeutic_class = db.Column(db.String(60), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    list_verified_at = db.Column(db.DateTime, nullable=True)
    list_verified_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.UniqueConstraint('generic_key', 'brand_name', 'strength', 'form', name='uq_medicine_identity'),
        db.CheckConstraint("tpg_list IN ('O','A','B','C')", name='ck_med_list'),
        db.CheckConstraint("schedule IN ('none','H','H1','X','NDPS')", name='ck_med_schedule'),
        db.CheckConstraint("schedule NOT IN ('X','NDPS') OR is_controlled", name='ck_med_controlled'),
    )

    @property
    def label(self):
        """GENERIC NAME strength form, generic in capitals (design 3.1)."""
        return f'{self.generic_name.upper()} {self.strength} {self.form}'.strip()


class InventoryBatch(db.Model):
    """Stock of one medicine batch at one institution. Changed only together with a ledger row (design 4.3)."""
    __tablename__ = 'inventory_batches'
    id = db.Column(db.Integer, primary_key=True)
    institution_key = db.Column(db.String(100), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='RESTRICT'), nullable=False)
    batch_no = db.Column(db.String(40), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    quantity_on_hand = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=True)
    supplier = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(12), nullable=False, default='active')
    received_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    medicine = db.relationship('Medicine')

    __table_args__ = (
        db.UniqueConstraint('institution_key', 'medicine_id', 'batch_no', 'expiry_date', name='uq_batch_identity'),
        db.CheckConstraint('quantity_on_hand >= 0', name='ck_batch_qty'),
        db.CheckConstraint("status IN ('active','quarantined','closed')", name='ck_batch_status'),
        db.Index('idx_batch_fefo', 'institution_key', 'medicine_id', 'status', 'expiry_date'),
    )


class ReorderRule(db.Model):
    """Per-institution reorder level of a medicine."""
    __tablename__ = 'reorder_rules'
    id = db.Column(db.Integer, primary_key=True)
    institution_key = db.Column(db.String(100), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='RESTRICT'), nullable=False)
    reorder_level = db.Column(db.Integer, nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.UniqueConstraint('institution_key', 'medicine_id', name='uq_reorder_inst_medicine'),
        db.CheckConstraint('reorder_level >= 0', name='ck_reorder_level'),
    )


class Prescription(db.Model):
    """A prescription. Drafts are editable; an issued one is immutable except status and dispensing (design 3)."""
    __tablename__ = 'prescriptions'
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    medication_name = db.Column(db.String(200), nullable=True)  # legacy rows only
    dosage = db.Column(db.String(100), nullable=True)  # legacy rows only
    instructions = db.Column(db.Text, nullable=True)  # legacy rows only
    issue_date = db.Column(db.DateTime, nullable=True)  # NULL for drafts; naive UTC
    expiry_date = db.Column(db.DateTime, nullable=True)  # expiry instant, naive UTC
    number = db.Column(db.String(24), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='draft')
    institution_key = db.Column(db.String(100), nullable=True)
    institution_name = db.Column(db.String(100), nullable=True)
    doctor_name = db.Column(db.String(100), nullable=True)
    doctor_reg_no = db.Column(db.String(20), nullable=True)
    doctor_council = db.Column(db.String(100), nullable=True)
    doctor_specialisation = db.Column(db.String(100), nullable=True)
    patient_name = db.Column(db.String(100), nullable=True)
    consult_appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True)
    tpg_context = db.Column(db.String(10), nullable=True)
    same_condition_attested = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    diagnosis = db.Column(db.String(120), nullable=True)
    allergies_status = db.Column(db.String(12), nullable=True)
    allergies = db.Column(db.String(300), nullable=True)
    current_meds_status = db.Column(db.String(12), nullable=True)
    current_meds = db.Column(db.String(300), nullable=True)
    warnings_ack = db.Column(db.JSON, nullable=True)
    consent_version = db.Column(db.String(20), nullable=True)
    amends_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='SET NULL'), nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancelled_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    cancel_reason = db.Column(db.String(20), nullable=True)
    dispense_requested_at = db.Column(db.DateTime, nullable=True)
    client_request_id = db.Column(db.String(64), nullable=True)
    issue_request_id = db.Column(db.String(64), nullable=True)
    expiry_days = db.Column(db.Integer, nullable=True)  # validity the doctor chose; the draft keeps it until issue
    row_version = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    provider = db.relationship('User', foreign_keys=[provider_id],
                               backref=db.backref('prescribed_prescriptions', passive_deletes=True))
    patient = db.relationship('User', foreign_keys=[patient_id],
                              backref=db.backref('received_prescriptions', cascade='all, delete-orphan', passive_deletes=True))
    items = db.relationship('PrescriptionItem', backref='prescription', cascade='all, delete-orphan',
                            passive_deletes=True, order_by='PrescriptionItem.line_no')

    __table_args__ = (
        db.CheckConstraint("status IN ('draft','issued','partially_dispensed','dispensed','cancelled','expired','legacy')",
                           name='ck_rx_status'),
        db.CheckConstraint(f'allergies_status IS NULL OR allergies_status IN {_THREE}', name='ck_rx_allergies'),
        db.CheckConstraint(f'current_meds_status IS NULL OR current_meds_status IN {_THREE}', name='ck_rx_current_meds'),
        db.CheckConstraint("cancel_reason IS NULL OR cancel_reason IN "
                           "('error','patient_request','clinical_change','amended','system')", name='ck_rx_cancel_reason'),
        db.Index('uq_rx_number', 'number', unique=True),
        db.Index('idx_rx_provider_status', 'provider_id', 'status'),
        db.Index('idx_rx_patient_status', 'patient_id', 'status'),
        db.Index('idx_rx_inst_status_req', 'institution_key', 'status', 'dispense_requested_at'),
        db.Index('uq_rx_provider_crid', 'provider_id', 'client_request_id', unique=True),
        db.Index('uq_rx_provider_issue_rid', 'provider_id', 'issue_request_id', unique=True),
    )

    def __repr__(self):
        return f'<Prescription {self.id} {self.status}>'


class PrescriptionItem(db.Model):
    """One medicine line of a prescription (design 3.1)."""
    __tablename__ = 'prescription_items'
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=False)
    line_no = db.Column(db.Integer, nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='RESTRICT'), nullable=False)
    medicine_label = db.Column(db.String(200), nullable=True)
    tpg_list = db.Column(db.String(1), nullable=True)
    dose_text = db.Column(db.String(60), nullable=False)
    frequency = db.Column(db.String(60), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    quantity_dispensed = db.Column(db.Integer, nullable=False, default=0)
    instructions = db.Column(db.String(200), nullable=True)

    medicine = db.relationship('Medicine')

    __table_args__ = (
        db.UniqueConstraint('prescription_id', 'line_no', name='uq_rxi_line'),
        db.UniqueConstraint('prescription_id', 'medicine_id', name='uq_rxi_medicine'),
        db.CheckConstraint('duration_days BETWEEN 1 AND 90', name='ck_rxi_duration'),
        db.CheckConstraint('quantity BETWEEN 1 AND 500', name='ck_rxi_qty'),
        db.CheckConstraint('quantity_dispensed >= 0 AND quantity_dispensed <= quantity', name='ck_rxi_dispensed'),
    )


_SIGN = ("(kind IN ('receive','return') AND delta > 0) OR (kind IN ('dispense','expire') AND delta < 0) "
         "OR (kind = 'adjust' AND delta <> 0)")
_REASONS = ("'purchase','donation','transfer_in','opening_stock','dispense','dispense_reversed',"
            "'count_correction','damaged','lost','recalled','expired_writeoff'")


class InventoryTransaction(db.Model):
    """Append-only stock ledger. No code updates or deletes these rows (design 4.1)."""
    __tablename__ = 'inventory_transactions'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('inventory_batches.id', ondelete='RESTRICT'), nullable=False, index=True)
    delta = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_items.id', ondelete='SET NULL'), nullable=True)
    rx_number = db.Column(db.String(24), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    reason_code = db.Column(db.String(24), nullable=False)
    group_ref = db.Column(db.String(36), nullable=True, index=True)
    reverses_id = db.Column(db.Integer, db.ForeignKey('inventory_transactions.id'), nullable=True)
    dispenser_label = db.Column(db.String(140), nullable=True)
    idempotency_key = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    batch = db.relationship('InventoryBatch')

    __table_args__ = (
        db.CheckConstraint("kind IN ('receive','dispense','adjust','expire','return')", name='ck_invtx_kind'),
        db.CheckConstraint(_SIGN, name='ck_invtx_sign'),
        db.CheckConstraint(f'reason_code IN ({_REASONS})', name='ck_invtx_reason'),
        db.Index('uq_invtx_idem', 'idempotency_key', unique=True),
        db.Index('uq_invtx_reverses', 'reverses_id', unique=True),
    )
