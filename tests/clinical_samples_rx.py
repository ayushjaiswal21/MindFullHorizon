"""Sample template contexts for the provider prescribing screens (shapes from docs/CLINICAL_DESIGN.md 5.5 and 5.6).

CASES[template][case_name] is a dict of render_template keyword arguments.
"""
ISO = '2026-11-24T08:30:00Z'
URLS = {'patients': '/provider/api/rx/patients', 'eligibility': '/provider/api/rx/eligibility', 'medicines': '/provider/api/rx/medicines',
        'drafts': '/provider/api/rx/prescriptions', 'detail_template': '/provider/prescriptions/0', 'appointments': '/provider/appointments',
        'profile': '/provider/prescribing-profile'}
LIMITS = {'max_items': 6, 'max_days': 14, 'expiry_days_max': 30}
ITEM = {'line_no': 1, 'medicine_id': 12, 'medicine_label': 'ESCITALOPRAM 10 mg tablet', 'tpg_list': 'A', 'dose_text': '1 tablet',
        'frequency': 'once daily', 'duration_days': 14, 'quantity': 14, 'quantity_dispensed': 4, 'instructions': 'After breakfast'}
RX = {'id': 90, 'row_version': 3, 'status': 'issued', 'effective_status': 'issued', 'number': 'RX2611-7K3M9QX4PD2',
      'patient': {'id': 7, 'name': 'A. Student'}, 'consult_appointment_id': 41, 'tpg_context': 'first', 'diagnosis': 'F41.1',
      'allergies_status': 'listed', 'allergies': 'Penicillin', 'current_meds_status': 'unknown', 'current_meds': None, 'expiry_days': 30,
      'items': [ITEM], 'issued_at': ISO, 'valid_until': '2026-12-24T18:29:59Z', 'cancel_reason': None,
      'dispense_requested_at': ISO, 'collection': 'partial', 'doctor_name': 'Dr. Meera Rao', 'doctor_reg_no': 'MH12345',
      'doctor_council': 'Maharashtra Medical Council', 'doctor_specialisation': 'Psychiatry', 'institution_name': 'Test University',
      'consult_started_at': ISO}
DRAFT = dict(RX, status='draft', effective_status='draft', number=None, issued_at=None, valid_until=None, items=[dict(ITEM, quantity_dispensed=0)])
CANCELLED = dict(RX, status='cancelled', effective_status='cancelled', cancelled_at=ISO, cancel_reason='error')
EXPIRED = dict(RX, status='issued', effective_status='expired')
PRINT = {'site_url': 'https://example.org', 'printed_at': ISO}
PROFILE = {'registration_number': 'MH12345', 'council': 'Maharashtra Medical Council', 'registered_since': 2011,
           'specialisation': 'Psychiatry', 'status': 'pending', 'submitted_at': ISO, 'review_due_at': None}


def _section(state):
    return {'rx_section': {'show': True, 'state': state, 'review_due_at': '2027-11-24T00:00:00Z' if state == 'verified' else None}}


CASES = {
    'provider_rx/_dashboard_section.html': {'pending': _section('pending'), 'rejected': _section('rejected'), 'suspended': _section('suspended'),
                                            'lapsed': _section('lapsed'), 'verified': _section('verified')},
    'provider_rx/prescribe.html': {'empty': {'config': URLS, 'patient': None, 'draft': None, 'limits': LIMITS, 'rx_texts': {}},
                                   'full': {'config': URLS, 'patient': RX['patient'], 'draft': DRAFT, 'limits': LIMITS, 'rx_texts': {}}},
    'provider_rx/list.html': {'empty': {'tab': 'draft', 'config': {}}, 'full': {'tab': 'issued', 'config': {}}, 'closed': {'tab': 'closed', 'config': {}}},
    'provider_rx/detail.html': {'empty': {'rx': dict(DRAFT, items=[], number=None), 'can_cancel': False, 'can_amend': False, 'config': {}},
                                'full': {'rx': RX, 'can_cancel': True, 'can_amend': True, 'config': {}},
                                'cancelled': {'rx': CANCELLED, 'can_cancel': False, 'can_amend': False, 'config': {}}},
    'provider_rx/print.html': {'empty': dict(PRINT, rx=dict(RX, items=[], diagnosis=None, allergies_status='unknown')),
                               'full': dict(PRINT, rx=RX), 'cancelled': dict(PRINT, rx=CANCELLED), 'expired': dict(PRINT, rx=EXPIRED)},
    'provider_rx/profile.html': {'empty': {'profile': None, 'state': None, 'form': {}, 'errors': {}},
                                 'full': {'profile': dict(PROFILE, status='verified', review_due_at='2027-11-24T00:00:00Z'), 'state': 'verified', 'form': {}, 'errors': {}},
                                 'errors': {'profile': PROFILE, 'state': 'pending', 'form': {'registration_number': 'x', 'council': 'ab', 'registered_since': '1900'},
                                            'errors': {'registration_number': 'Enter 4 to 20 characters.', 'council': 'Enter at least 3 characters.',
                                                       'registered_since': 'Enter a year from 1950.'}}},
}
