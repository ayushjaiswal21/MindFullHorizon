"""Sample template contexts for the admin screens (shapes from docs/CLINICAL_DESIGN.md 5.5 and 5.6).

CASES[template][case_name] is a dict of render_template keyword arguments. Every template has an 'empty' and a
'full' case. Names ending in '_nodesk' render the read-only admin. Patient names appear only on the dispensing desk page.
"""
META = {'page': 1, 'per_page': 20, 'total': 41, 'has_next': True}
META_EMPTY = {'page': 1, 'per_page': 20, 'total': 0, 'has_next': False}
ISO = '2026-11-24T08:30:00Z'
BASE = {'desk': True, 'admin_name': 'Asha Admin', 'institution': 'Test University'}

D_FULL = {
    'pending_verifications': 2, 'staff': {'counsellors': 3, 'doctors_verified': 1, 'doctors_pending': 2},
    'patients': {'total': 120}, 'summary': {'total_patients': 120, 'patient_engagement': 62.5, 'completion_rate': 80, 'avg_screen_time': 4.2},
    'crisis_overdue': {'any': True, 'count': 6}, 'stock': {'low': 2, 'out': 1, 'near_expiry': 3, 'awaiting_writeoff': 1},
    'review_due': 1, 'rx_month': 14, 'dispensed_today': 3, 'unread_messages': 4,
    'recent_audit': [{'created_at': ISO, 'action': 'prescriber_verify', 'target_type': 'prescriber_profile', 'target_id': 3}],
}
D_EMPTY = {
    'pending_verifications': 0, 'staff': {'counsellors': 0, 'doctors_verified': 0, 'doctors_pending': 0}, 'patients': {'total': None},
    'summary': {'aggregates_hidden': True}, 'crisis_overdue': {'any': False, 'count': None},
    'stock': {'low': 0, 'out': 0, 'near_expiry': 0, 'awaiting_writeoff': 0}, 'review_due': 0, 'rx_month': None,
    'dispensed_today': 0, 'unread_messages': 0, 'recent_audit': [],
}
STAFF = [
    {'id': 5, 'name': 'Dr. Meera Rao', 'email': 'meera@example.org', 'provider_type': 'doctor', 'institution_typed': 'Test University',
     'created_at': ISO, 'deactivated': False, 'verification_state': 'pending'},
    {'id': 6, 'name': 'Ravi Counsellor', 'email': 'ravi@example.org', 'provider_type': 'counsellor', 'institution_typed': 'test university ',
     'created_at': ISO, 'deactivated': True, 'verification_state': None},
]
VERIF = [{'id': 3, 'user_name': 'Dr. Meera Rao', 'email': 'meera@example.org', 'registration_number': 'MH12345', 'council': 'Maharashtra Medical Council',
          'registered_since': 2011, 'specialisation': 'Psychiatry', 'status': 'pending', 'submitted_at': ISO, 'review_due_at': None}]
CHECKLIST = [{'key': 'name_year_council', 'text': 'The entry name, year and State Medical Council match.'},
             {'key': 'not_removed', 'text': 'The doctor is not on the NMC removed-doctors list.'}]
MEDS = [
    {'id': 12, 'label': 'ESCITALOPRAM 10 mg tablet', 'form': 'tablet', 'route': 'oral', 'tpg_list': 'A', 'schedule': 'none',
     'therapeutic_class': 'SSRI', 'active': True, 'verified': True, 'is_demo': False, 'updated_by_id': 1},
    {'id': 13, 'label': 'Democillin 10 mg tablet (DEMO)', 'form': 'tablet', 'route': 'oral', 'tpg_list': 'C', 'schedule': 'H',
     'therapeutic_class': None, 'active': False, 'verified': False, 'is_demo': True, 'updated_by_id': 9},
    {'id': 14, 'label': 'Fictapine 5 mg tablet (DEMO)', 'form': 'tablet', 'route': 'oral', 'tpg_list': 'B', 'schedule': 'H',
     'therapeutic_class': None, 'active': True, 'verified': False, 'is_demo': True, 'updated_by_id': 9},
]
STOCK = [{'medicine_id': 12, 'label': 'ESCITALOPRAM 10 mg tablet', 'usable': 120, 'expired': 10, 'reorder_level': 50, 'status': 'in_stock'},
         {'medicine_id': 14, 'label': 'Fictapine 5 mg tablet (DEMO)', 'usable': 3, 'expired': 0, 'reorder_level': None, 'status': 'low'},
         {'medicine_id': 15, 'label': 'Demoxetine 20 mg capsule (DEMO)', 'usable': 0, 'expired': 0, 'reorder_level': 10, 'status': 'out'}]
BATCHES = [
    {'id': 5, 'medicine_id': 12, 'label': 'ESCITALOPRAM 10 mg tablet', 'batch_no': 'B123', 'expiry_date': '2027-03-31', 'quantity_on_hand': 120, 'supplier': 'Acme', 'status': 'active', 'days_left': 127},
    {'id': 6, 'medicine_id': 12, 'label': 'ESCITALOPRAM 10 mg tablet', 'batch_no': 'B100', 'expiry_date': '2026-11-01', 'quantity_on_hand': 10, 'supplier': None, 'status': 'active', 'days_left': -23},
    {'id': 7, 'medicine_id': 14, 'label': 'Fictapine 5 mg tablet (DEMO)', 'batch_no': 'B200', 'expiry_date': '2026-12-20', 'quantity_on_hand': 3, 'supplier': 'Acme', 'status': 'quarantined', 'days_left': 26},
]
REASONS = [('count_correction', 'Count correction'), ('damaged', 'Damaged'), ('lost', 'Lost'), ('recalled', 'Recalled')]
RX = {'id': 90, 'number': 'RX2611-7K3M9QX4PD2', 'status': 'issued', 'patient_name': 'A. Student', 'doctor_name': 'Dr. Meera Rao', 'valid_until': '2026-12-24T18:29:59Z',
      'warnings': ['Stock is short for line 1.'],
      'items': [{'item_id': 301, 'medicine_label': 'ESCITALOPRAM 10 mg tablet', 'quantity': 14, 'quantity_dispensed': 0, 'remaining': 14},
                {'item_id': 302, 'medicine_label': 'Fictapine 5 mg tablet (DEMO)', 'quantity': 7, 'quantity_dispensed': 7, 'remaining': 0}]}
AUDIT = [{'created_at': ISO, 'actor_name': 'Asha Admin', 'actor_role': 'admin', 'action': 'view_audit_log', 'target_type': 'audit_log', 'target_id': None, 'meta': {'n': 5}},
         {'created_at': ISO, 'actor_name': None, 'actor_role': None, 'action': 'denied', 'target_type': 'route', 'target_id': None, 'meta': 'code=role'}]
MSGS = [{'id': 1, 'name': 'Priya', 'email': 'priya@example.org', 'subject': 'Question about privacy', 'created_at': ISO, 'read': False},
        {'id': 2, 'name': 'Sam', 'email': 'sam@example.org', 'subject': None, 'created_at': ISO, 'read': True}]
ANNUAL = {'year': 2026, 'institution': 'Test University', 'generated_at': ISO, 'sections': [
    {'title': 'Students', 'metrics': [{'name': 'Registered', 'value': 120, 'note': None}, {'name': 'Active', 'value': None, 'note': 'suppressed (fewer than 5 people)'}]},
    {'title': 'Prescriptions', 'metrics': [{'name': 'Issued', 'value': 14, 'note': ''}]}]}

CASES = {
    'admin/login.html': {'empty': {'form': {}}, 'full': {'form': {'email': 'asha@example.org'}}},
    'admin/dashboard.html': {'empty': dict(BASE, d=D_EMPTY), 'full': dict(BASE, d=D_FULL), 'full_nodesk': dict(BASE, d=D_FULL, desk=False)},
    'admin/staff.html': {'empty': dict(BASE, rows=[], meta=META_EMPTY, filters={}), 'empty_filtered': dict(BASE, rows=[], meta=META_EMPTY, filters={'type': 'doctor'}),
                         'full': dict(BASE, rows=STAFF, meta=META, filters={'type': '', 'status': 'active'})},
    'admin/verification.html': {'empty': dict(BASE, tab='pending', counts={}, rows=[], meta=META_EMPTY),
                                'empty_other': dict(BASE, tab='rejected', counts={'rejected': 0}, rows=[], meta=META_EMPTY),
                                'full': dict(BASE, tab='pending', counts={'pending': 1, 'verified': 2}, rows=VERIF, meta=META)},
    'admin/verification_detail.html': {
        'empty': dict(BASE, p=dict(VERIF[0], notes=None, verified_by_name=None, verified_at=None), register_url='https://www.nmc.org.in/x', blacklist_url='https://www.nmc.org.in/y', checklist=[], actions=[]),
        'full': dict(BASE, p=dict(VERIF[0], notes='NMR search, match', verified_by_name='Asha Admin', verified_at=ISO), register_url='https://www.nmc.org.in/x',
                     blacklist_url='https://www.nmc.org.in/y', checklist=CHECKLIST, actions=['verify', 'reject', 'suspend', 'reinstate'])},
    'admin/catalogue.html': {'empty': dict(BASE, rows=[], meta=META_EMPTY, filters={}, four_eyes=False, me_id=1),
                             'full': dict(BASE, rows=MEDS, meta=META, filters={'q': 'esc'}, four_eyes=True, me_id=9)},
    'admin/catalogue_form.html': {'empty': dict(BASE, medicine=None, lists=[('O', 'Over the counter'), ('A', 'Allowed'), ('B', 'Follow-up'), ('C', 'Blocked')], schedules=['none', 'H', 'H1', 'X', 'NDPS'], errors={}),
                                  'full': dict(BASE, medicine=dict(MEDS[0], generic_name='Escitalopram', brand_name='', strength='10 mg'),
                                               lists=[{'code': 'A', 'text': 'Allowed'}, {'code': 'C', 'text': 'Blocked'}], schedules=[{'code': 'none', 'text': 'None'}], errors={'strength': 'Enter a strength.'})},
    'admin/inventory.html': {'empty': dict(BASE, rows=[], meta=META_EMPTY, stats={}, reasons=REASONS, config={}),
                             'empty_nodesk': dict(BASE, desk=False, rows=[], meta=META_EMPTY, stats={}, reasons=REASONS, config={}),
                             'full': dict(BASE, rows=STOCK, meta=META, stats={'low': 1, 'out': 1, 'near_expiry': 2, 'awaiting_writeoff': 1}, reasons=REASONS, config={}),
                             'full_nodesk': dict(BASE, desk=False, rows=STOCK, meta=META, stats={'low': 1}, reasons=REASONS, config={})},
    'admin/batches.html': {'empty': dict(BASE, rows=[], meta=META_EMPTY, reasons=REASONS, config={}),
                           'full': dict(BASE, rows=BATCHES, meta=META, reasons=dict(REASONS), config={}),
                           'full_nodesk': dict(BASE, desk=False, rows=BATCHES, meta=META, reasons=REASONS, config={})},
    'admin/receive.html': {'empty': dict(BASE, rows=[], meta=META_EMPTY, stats={}, reasons=REASONS, config={}),
                           'full': dict(BASE, rows=[], meta=META_EMPTY, stats={}, reasons=REASONS, config={}), 'full_nodesk': dict(BASE, desk=False, reasons=REASONS, config={})},
    'admin/dispensing.html': {'empty': dict(BASE, queue=[], config={}),
                              'full': dict(BASE, queue=[{'id': 90, 'number': RX['number'], 'initials': 'A. S.', 'items': 2, 'requested_at': ISO}], config={})},
    'admin/dispensing_detail.html': {'empty': dict(BASE, rx=dict(RX, items=[], warnings=[], status='cancelled'), config={}),
                                     'full': dict(BASE, rx=RX, config={}, transactions=[{'tx_id': 7, 'label': 'ESCITALOPRAM 10 mg tablet', 'quantity': 7, 'created_at': ISO, 'reversible': True},
                                                                                   {'tx_id': 8, 'label': 'Fictapine', 'quantity': 1, 'created_at': ISO, 'reversible': False}])},
    'admin/reports.html': {'empty': dict(BASE, tab='stock', config={}), 'full': dict(BASE, tab='log', config={}),
                           'usage': dict(BASE, tab='usage', config={}), 'expiring_nodesk': dict(BASE, tab='expiring', desk=False, config={}),
                           'log_nodesk': dict(BASE, tab='log', desk=False, config={})},
    'admin/audit.html': {'empty': dict(BASE, rows=[], meta=META_EMPTY, filters={}, actions=['denied'], staff=[]),
                         'full': dict(BASE, rows=AUDIT, meta=META, filters={'action': 'denied', 'actor': '1', 'from': '2026-11-01', 'to': '2026-11-24'},
                                      actions=['denied', 'view_audit_log'], staff=[(1, 'Asha Admin'), {'id': 2, 'name': 'Ravi'}])},
    'admin/annual.html': {'empty': dict(BASE, report=dict(ANNUAL, sections=[]), years=[2026, 2025]), 'full': dict(BASE, report=ANNUAL, years=[2026, 2025])},
    'admin/messages.html': {'empty': dict(BASE, rows=[], meta=META_EMPTY, selected=None),
                            'full': dict(BASE, rows=MSGS, meta=META, selected=dict(MSGS[0], body='Hello,\nIs my data shared?')),
                            'read': dict(BASE, rows=MSGS, meta=META_EMPTY, selected=dict(MSGS[1], body='Thanks.'))},
}
