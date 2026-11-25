"""Patient journal: AI suggestions and the journal page (crisis text runs through the same rule-based check as mood/chat)."""
import logging
from flask import render_template, session, redirect, url_for, flash, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import JournalEntry
from decorators import patient_required
from utils import idempotency as idem
from utils.gamification import award_points
from utils.ai_cap import run_capped
from utils.pagination import paginate
from utils.sentiment import TextBlob, TEXTBLOB_AVAILABLE
import ai.service as ai_service

from . import patient_bp, AI_REQUEST_CAP

logger = logging.getLogger(__name__)


def get_ai_journal_suggestions(title, content):
    """Get AI-powered suggestions for journal entries with optimized prompts."""
    try:
        # Simple sentiment check for context (optional, can be improved)
        sentiment = "Neutral"
        if TEXTBLOB_AVAILABLE:
             try:
                 blob = TextBlob(content)
                 if blob.sentiment.polarity > 0.1: sentiment = "Positive"
                 elif blob.sentiment.polarity < -0.1: sentiment = "Negative"
             except: pass

        # Use the dedicated AI service function
        ok, suggestions = run_capped(ai_service.generate_journal_insights, title, content, sentiment, seconds=AI_REQUEST_CAP)
        if not ok or not isinstance(suggestions, str):
            raise RuntimeError('ai unavailable')

        # Clean up and format the response for better readability
        suggestions = suggestions.strip()[:800]  # Limit length

        # Ensure we have meaningful content
        if len(suggestions) < 50:  # Too short, probably error
            suggestions = "Thank you for sharing your thoughts. Consider discussing these feelings with a trusted friend or mental health professional."

        return suggestions

    except Exception as e:
        logger.warning(f"AI suggestion generation failed: {e}")
        return "Thank you for sharing your thoughts. Consider discussing these feelings with a trusted friend or mental health professional."


@patient_bp.route('/journal', methods=['GET', 'POST'])
@patient_required
def patient_journal():
    """Journal entries page for patients."""
    # Ensure user is logged in and has valid session
    if 'user_id' not in session:
        flash('Please log in to access your journal.', 'error')
        return redirect(url_for('auth.login'))

    user_id = session['user_id']

    if request.method == 'POST':
        key = idem.get_key()
        if idem.existing(JournalEntry, user_id, key):  # replay: already saved
            flash('Journal entry saved successfully!', 'success')
            return redirect(url_for('patient.patient_journal'))
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        if not title or not content:
            flash('Both title and content are required.', 'error')
            return redirect(url_for('patient.patient_journal'))

        if len(title) > 100:
            flash('Title must be less than 100 characters.', 'error')
            return redirect(url_for('patient.patient_journal'))

        if len(content) > 5000:
            flash('Content must be less than 5000 characters.', 'error')
            return redirect(url_for('patient.patient_journal'))

        # Perform sentiment analysis
        sentiment_result = 'Neutral'  # Default fallback
        if TEXTBLOB_AVAILABLE:
            try:
                blob = TextBlob(content)
                polarity = blob.sentiment.polarity
                if polarity > 0.1:
                    sentiment_result = 'Positive'
                elif polarity < -0.1:
                    sentiment_result = 'Negative'
                else:
                    sentiment_result = 'Neutral'
            except Exception as e:
                logger.warning(f"Sentiment analysis failed: {e}")
                sentiment_result = 'Neutral'

        # Get AI suggestions for the journal entry
        ai_suggestions = get_ai_journal_suggestions(title, content)

        # O-02: rule-based check on the text; the event holds a code only, never the text. Same transaction as the entry.
        from utils.crisis import record_crisis, text_is_crisis_detailed
        from utils.helplines import helplines_text
        crisis, crisis_matched_via = text_is_crisis_detailed(f"{title}\n{content}")
        try:
            entry = JournalEntry(user_id=user_id, title=title, content=content, sentiment=sentiment_result,
                                 ai_suggestions=ai_suggestions, client_request_id=key)
            db.session.add(entry)
            if crisis:  # '_fuzzy' suffix = audit-only tag, hit via the edit-distance-1 layer, not an exact regex
                record_crisis(user_id, 'journal', 9, 'journal_self_harm_fuzzy' if crisis_matched_via == 'fuzzy' else 'journal_self_harm')
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            if isinstance(exc, IntegrityError) and idem.existing(JournalEntry, user_id, key):  # concurrent double submit
                flash('Journal entry saved successfully!', 'success')
                return redirect(url_for('patient.patient_journal'))
            logger.error("Journal save FAILED user=%s crisis=%s err=%s", user_id, crisis, type(exc).__name__)
            flash('Could not save your journal entry. Please try again.', 'error')
            if crisis:
                flash('You are not alone. If you are in danger call 112. Free support: ' + helplines_text(), 'warning')
            return redirect(url_for('patient.patient_journal'))

        # Award points for journaling
        if not crisis:  # no cheerful rewards right after a crisis flag
            award_points(user_id, 15, 'journal_entry', ref=f'journal:{entry.id}')

        flash('Journal entry saved successfully!', 'success')
        if crisis:
            flash('We noticed your words sound painful. You do not have to carry this alone. '
                  'If you are in danger call 112. Free support: ' + helplines_text(), 'warning')
        return redirect(url_for('patient.patient_journal'))

    # GET request - display journal entries
    # newest page first (?page=, ?per_page=, default 50, max 100), handed over oldest-to-newest (the template reverses)
    user_entries, journal_pagination = paginate(JournalEntry.query.filter_by(user_id=user_id)
                                                .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc()), default=50)
    user_entries.reverse()

    return render_template('patient_journal.html',
                         user_name=session['user_name'],
                         journal_entries=user_entries,
                         pagination=journal_pagination)
