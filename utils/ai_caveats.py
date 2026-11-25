"""Caveat copy for LLM-generated numeric scores (SYNTHESIS.md section 3(c) item c2: KEEP WITH STRONG CAVEAT).

These cover `ai.service.analyze_medication_adherence` (adherence score) and
`ai.service.generate_digital_detox_insights` (digital-detox score). Both are single-item,
single-student estimates a reader can sanity-check against the raw logged count shown beside
them -- never a validated clinical measurement. Per the synthesis's additional requirements:
show the raw logged-dates count next to every score, and never show the bare number to a
counsellor without this same caveat and count attached.
"""

ADHERENCE_CAVEAT = (
    "This number is an estimate written by an AI model from a few logged entries. "
    "It is not a clinical measurement and has not been checked against real adherence. "
    "Use the logged dates below to see what was actually recorded."
)

DETOX_CAVEAT = (
    "This score is an estimate written by an AI model from a few logged entries. "
    "It is not a clinical measurement. Use the logged screen-time entries below to see "
    "what was actually recorded."
)
