"""Clinical services (roles, prescriber verification, prescriptions, inventory, dispensing, reports).

Service functions flush but do not commit unless their docstring says so; routes own the transaction.
Contract: docs/CLINICAL_DESIGN.md.
"""
