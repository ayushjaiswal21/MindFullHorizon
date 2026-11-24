"""Fixed wording for the prescription feature, shared by the doctor, patient and print pages.

Source of truth: docs/CLINICAL_DESIGN.md sections 2.2, 3.3 to 3.6 and 4.4. Wording is copied verbatim from there.
Change a sentence here and it changes on every screen. Keep it plain; no claims the system cannot back up.
"""

ERX_CONSENT_TEXT = (
    "I agree that this doctor may issue me an electronic prescription through MindFull Horizon. "
    "The prescription shows my name, the diagnosis the doctor enters and the medicines. "
    "I can withdraw this at any time on the prescriptions page."
)

SAFETY_LINES = {
    # 3.5: shown with every warning block
    'interaction_check': ("This check finds the same medicine or the same class only. It is not a drug interaction "
                          "check. Check interactions yourself before issuing."),
    # 4.4: shown with availability badges
    'stock_guide': "Availability is a guide. Stock is not held for this prescription.",
    # 3.3: shown next to Start consult
    'consult_start': ("Starting a consult records that you are seeing this patient now. "
                      "Only start it while the consult is happening."),
    # 3.7 confirm dialog
    'immutable': "This cannot be edited after it is issued. You can cancel it or write a new one.",
    # 3.8 cancel dialog
    'cancel_visible': "The patient and the pharmacy desk will see it as cancelled",
    # 3.8 patient detail when the prescriber is suspended
    'not_dispensable': "This prescription cannot be dispensed right now. Contact your institution's pharmacy desk.",
    # 5.3 counsellor panel
    'meds_panel_help': ("Medicines are listed so you can take them into account. "
                        "Only a verified doctor can change a prescription."),
    'meds_panel_empty': "No medicines recorded for this patient.",
}

# Patient pages (5.2): plain-language explanation and honest limits.
PATIENT_EXPLAINER = (
    "A prescription here comes from a doctor at your college who saw you in a consultation, by video or in person. "
    "MindFull Horizon never prescribes medicine by itself, and the AI companion cannot prescribe or change a "
    "prescription."
)
PATIENT_PRIVACY_NOTE = (
    "Counsellors you have booked with can see the medicine names, doses and dates, not the diagnosis. "
    "Your doctor and the college pharmacy desk can see the full prescription."
)
LEGACY_WARNING = "Issued before doctor verification existed. Ask your doctor to issue it again."

EMPTY_ACTIVE = "No active prescriptions."
EMPTY_PAST = "No past prescriptions."
EMPTY_ALL = "No prescriptions yet. A doctor you have seen through MindFull Horizon can send one here."
CARE_TEAM_NOTE = "These people can see the information you share on this service."
CARE_TEAM_EMPTY = "You have not booked with anyone yet."
