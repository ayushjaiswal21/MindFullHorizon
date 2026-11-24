"""ServiceError and the fixed table of safe client messages (design 5.1). Exception text never reaches a client."""

MESSAGES = {
    # generic
    'bad_request': 'The request could not be understood.',
    'not_found': 'Not found.',
    'forbidden': 'You do not have permission to do this.',
    'validation': 'Please check the highlighted fields.',
    'field_required': 'This field is required.',
    'field_too_long': 'This text is too long.',
    'field_invalid': 'This value is not valid.',
    'idempotency_key_required': 'A valid Idempotency-Key header is required.',
    'rate_limited': 'Too many requests. Please wait and try again.',
    'conflict': 'This conflicts with a change made at the same time. Reload and try again.',
    # roles and verification
    'prescriber_not_verified': 'Your registration has not been verified, so you cannot prescribe.',
    'checks_incomplete': 'Every item on the checklist must be ticked.',
    'note_required': 'Write a short evidence note (10 to 500 characters).',
    'bad_transition': 'That status change is not allowed from the current status.',
    'registration_in_use': 'That registration number is already in use.',
    # prescriptions
    'no_consult': 'No qualifying consult was started in the allowed time window.',
    'no_consent': 'The patient has not allowed e-prescriptions.',
    'patient_not_assigned': 'This patient is not assigned to you.',
    'not_draft': 'This prescription has already been issued and cannot be edited.',
    'stale_draft': 'This draft was changed in another tab. Reload to continue.',
    'already_issued': 'This prescription was already issued.',
    'amended_rx_changed': 'The prescription being corrected was dispensed or cancelled in the meantime.',
    'warnings_unacknowledged': 'Please acknowledge every warning before issuing.',
    'too_many_items': 'Too many medicines in one prescription.',
    'duration_too_long': 'The duration is longer than allowed.',
    'no_items': 'Add at least one medicine.',
    'duplicate_medicine': 'The same medicine appears twice in this prescription.',
    'not_cancellable': 'This prescription can no longer be cancelled.',
    'not_amendable': 'Only an issued prescription can be corrected.',
    'not_sendable': 'This prescription cannot be sent to the pharmacy desk.',
    'medicine_inactive': 'This medicine is no longer in the catalogue.',
    'medicine_unverified': ('The list classification of this medicine has not been confirmed by a second '
                            'administrator, so it cannot be prescribed yet.'),
    'medicine_blocked_c': ('This medicine cannot be prescribed through teleconsultation (Telemedicine Practice '
                           'Guidelines 2020, List C). See the patient in person and prescribe outside this system.'),
    'medicine_controlled': ('This is a Schedule H1, Schedule X or NDPS medicine. It cannot be prescribed in this '
                            'system.'),
    'medicine_needs_followup': ('This is a List B medicine. It can be prescribed at a follow-up consult within 6 '
                                'months of an in-person consult for the same condition, or at an in-person consult.'),
    'medicine_demo_blocked': 'Demo medicine. Not for real prescriptions.',
    # catalogue and inventory
    'second_admin_required': 'A different administrator must confirm this classification.',
    'controlled_not_stocked': 'Controlled medicines cannot be stocked in this system.',
    'already_expired': 'This batch is already expired.',
    'would_go_negative': 'The stock cannot go below zero.',
    'bad_reason': 'Choose a valid reason.',
    'not_expired': 'Only an expired batch can be written off.',
    'import_duplicate': 'This file was already imported.',
    'import_invalid': 'The file has errors. Nothing was imported.',
    'import_too_large': 'The file is too large.',
    # dispensing
    'plan_stale': 'Stock or the prescription changed. Review the new plan and confirm again.',
    'rx_not_dispensable': 'This prescription cannot be dispensed (cancelled, expired, finished or not yours).',
    'nothing_to_dispense': 'There is nothing to dispense.',
    'identity_required': 'Confirm that you checked the patient identity and the prescription number.',
    'pharmacist_required': 'Enter the pharmacist name and registration number.',
    'bad_token': 'The dispensing plan is invalid or has expired. Prepare it again.',
    'not_reversible': 'This line cannot be reversed.',
    'bad_number': 'That prescription number is not valid.',
}

DEFAULT_HTTP = {'not_found': 404, 'forbidden': 403, 'validation': 422, 'field_required': 422, 'field_too_long': 422,
                'field_invalid': 422, 'prescriber_not_verified': 403}


class ServiceError(Exception):
    """A business-rule failure. `code` indexes MESSAGES; `http` is the status a route answers with."""

    def __init__(self, code, http=None, fields=None, **ctx):
        super().__init__(code)
        self.code = code
        self.http = http or DEFAULT_HTTP.get(code, 400)
        self.fields = fields or None
        self.ctx = ctx  # extra safe data for the body (warnings list, a fresh plan); never free text

    @property
    def message(self):
        return MESSAGES.get(self.code, MESSAGES['bad_request'])

    def body(self):
        out = {'success': False, 'error': self.code, 'message': self.message}
        if self.fields:
            out['fields'] = self.fields
        out.update(self.ctx)
        return out
