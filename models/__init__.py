"""Database models for the Mindful Horizon application.

Split by domain into this package (user, content, wellness_logs, gamification, clinical_core,
system, institutional_summary) so no single module holds the whole schema. Everything is
re-exported here so existing call sites (`from models import X`, `import models as m`) are
unaffected. models_clinical.py, models_wellbeing.py and models_followup.py stay as separate
top-level modules (already under the 300-line limit, already split by domain) and are imported
at the bottom exactly as before.
"""
import sqlite3
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine
from core.extensions import db  # noqa: F401  (re-exported: `from models import db` is used elsewhere)

# Module logger
logger = logging.getLogger(__name__)


@event.listens_for(Engine, 'connect')
def _sqlite_foreign_keys_on(dbapi_conn, _record):
    """SQLite ignores FOREIGN KEY / ON DELETE CASCADE unless this pragma is set per connection."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        cur.execute('PRAGMA foreign_keys=ON')
        cur.close()


from .user import User
from .content import BlogPost, BlogLike, BlogComment, BlogInsight, ContactMessage
from .wellness_logs import (
    Assessment, DigitalDetoxLog, RPMData, BreathingExerciseLog, YogaLog, MusicTherapyLog,
    ProgressRecommendation, BinauralTrack, MoodLog, JournalEntry, VoiceLog,
)
from .gamification import Gamification, PointsLedger
from .clinical_core import (
    ClinicalNote, InstitutionalAnalytics, Appointment, Goal, Medication, MedicationLog,
    CrisisEvent, ProviderPatient,
)
from .system import Notification, Job, AuditLog, ConsentRecord, AnalyticsEvent
from .institutional_summary import get_institutional_summary

from models_clinical import *  # noqa: E402,F401,F403  (same metadata; keeps `from models import Prescription` working)
from models_wellbeing import *  # noqa: E402,F401,F403  (safety plan, sleep log, reminder preference)
from models_followup import *  # noqa: E402,F401,F403  (post-crisis follow-up plans and steps)
