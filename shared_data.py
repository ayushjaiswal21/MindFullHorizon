# Shared data storage for patient features
# This module prevents circular imports between app.py and routes/patient.py

# In-memory storage for patient features (no database required)
patient_journal_entries = {}  # user_id -> list of journal entries
patient_voice_logs_data = {}  # user_id -> list of voice log entries
