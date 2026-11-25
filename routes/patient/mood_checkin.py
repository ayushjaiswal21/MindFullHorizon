"""Daily mood check-in. No points or streak: mood scores are never gamified."""
import logging
from flask import session, request, jsonify
from sqlalchemy.exc import IntegrityError

from core.extensions import db
from models import MoodLog, Assessment, User
from core.decorators import patient_required
from utils import idempotency as idem
from utils.timeutil import utcnow

from . import patient_bp

logger = logging.getLogger(__name__)


@patient_bp.route('/api/save-mood', methods=['POST'])
@patient_required
def save_mood():
    """Daily mood check-in for the session user. No points or streak: mood scores are never gamified."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    mood = data.get('mood')
    if isinstance(mood, str) and mood.strip().isdigit():
        mood = int(mood)
    if isinstance(mood, bool) or not isinstance(mood, int) or not 1 <= mood <= 10:
        return jsonify({'success': False, 'message': 'Mood must be a whole number from 1 to 10'}), 400
    notes = str(data.get('notes') or '').strip()[:500] or None

    # O-06: run free-text notes through the same rule-based check journal/chat use. The event holds a code
    # only, never the text. Mood scores stay ungamified either way (no points/streak here, crisis or not).
    from utils.crisis import record_crisis, text_is_crisis_detailed
    from utils.helplines import helplines_text
    crisis, crisis_matched_via = text_is_crisis_detailed(notes) if notes else (False, None)

    user_id = session['user_id']
    key = idem.get_key()
    saved = jsonify({'success': True, 'message': 'Mood saved. Thanks for checking in.'})
    if idem.existing(MoodLog, user_id, key):  # replay: same 200 body, no second row
        return saved
    try:
        db.session.add(MoodLog(user_id=user_id, mood_score=mood, notes=notes, client_request_id=key))
        # Same entry as a 'Daily Mood' assessment: the trend/progress code reads that type.
        db.session.add(Assessment(user_id=user_id, assessment_type='Daily Mood', score=mood,
                                  responses={'mood': mood, 'notes': notes or ''}, client_request_id=key))
        user = db.session.get(User, user_id)
        if user:
            user.last_assessment_at = utcnow()
        if crisis:  # '_fuzzy' suffix = audit-only tag, hit via the edit-distance-1 layer, not an exact regex
            record_crisis(user_id, 'mood', 9, 'mood_self_harm_fuzzy' if crisis_matched_via == 'fuzzy' else 'mood_self_harm')
        db.session.commit()
        if crisis:
            return jsonify({'success': True,
                            'message': 'We noticed your words sound painful. You do not have to carry this alone. '
                                        'If you are in danger call 112. Free support: ' + helplines_text()})
        return saved
    except IntegrityError:
        db.session.rollback()
        if idem.existing(MoodLog, user_id, key):  # concurrent double submit
            return saved
        logger.exception('Error saving mood')
        return jsonify({'success': False, 'message': 'Could not save your mood. Please try again.'}), 500
    except Exception:
        db.session.rollback()
        logger.exception('Error saving mood')
        return jsonify({'success': False, 'message': 'Could not save your mood. Please try again.'}), 500
