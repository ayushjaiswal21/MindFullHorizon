"""PHQ-9 / GAD-7 assessment page, question bank and the save-assessment API (server-side scoring)."""
import json
import logging
import os
from flask import render_template, session, flash, request, jsonify
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import User, Assessment
from decorators import patient_required, login_required
from utils import idempotency as idem
from utils.ai_cap import run_capped
from utils.timeutil import utcnow
import ai.service as ai_service

from . import patient_bp, AI_REQUEST_CAP

logger = logging.getLogger(__name__)


@patient_bp.route('/api/assessment/questions/<assessment_type>')
@login_required
@patient_required
def get_assessment_questions(assessment_type):
    try:
        questions_file_path = os.path.join(os.getcwd(), 'static', 'questions.json')

        if not os.path.exists(questions_file_path):
            return jsonify({'success': False, 'message': 'Assessment questions file not found.'}), 500

        with open(questions_file_path, 'r') as f:
            all_questions = json.load(f)

        questions = all_questions.get(assessment_type)

        if questions:
            return jsonify({'success': True, 'questions': questions})
        else:
            return jsonify({'success': False, 'message': 'Invalid assessment type.'}), 404

    except Exception:
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500


@patient_bp.route('/assessment')
@login_required
@patient_required
def assessment():
    try:
        user_id = session['user_id']
        assessment_objects = Assessment.query.filter_by(user_id=user_id).order_by(Assessment.created_at.desc()).limit(500).all()

        assessments = []
        for assessment in assessment_objects:
            assessment_dict = {
                'id': assessment.id,
                'user_id': assessment.user_id,
                'assessment_type': assessment.assessment_type,
                'score': assessment.score,
                'responses': assessment.responses,
                'created_at': assessment.created_at.isoformat() if assessment.created_at else None,
                'ai_insights': {}
            }

            if assessment.ai_insights:
                if isinstance(assessment.ai_insights, str):
                    try:
                        assessment_dict['ai_insights'] = json.loads(assessment.ai_insights)
                    except json.JSONDecodeError:
                        assessment_dict['ai_insights'] = {}
                else:
                    assessment_dict['ai_insights'] = assessment.ai_insights

            assessments.append(assessment_dict)

        latest_insights = None
        if assessments:
            latest_insights = assessments[0].get('ai_insights')

        return render_template('assessment.html',
                               user_name=session['user_name'],
                               assessments=assessments,
                               latest_insights=latest_insights)
    except Exception:
        flash('Error loading assessments. Please try again.', 'error')
        return render_template('assessment.html',
                               user_name=session['user_name'],
                               assessments=[],
                               latest_insights=None)


def _assessment_replay(a):
    """The save-assessment response rebuilt from the stored row (score and band are deterministic)."""
    from ai.scoring import score_assessment
    from utils.helplines import get_helplines
    result = score_assessment(a.assessment_type, a.responses)
    insights = json.loads(a.ai_insights) if a.ai_insights else {}
    crisis = bool(result.get('item9_positive') or result['severe'])
    return jsonify({
        'success': True, 'message': 'Assessment saved successfully', 'assessment_id': a.id, 'score': a.score,
        'band': result['band'], 'ai_insights': insights,
        'ai_insights_generated': not crisis and not str(insights.get('summary', '')).startswith('AI insights are currently unavailable'),
        'crisis': crisis, 'helplines': get_helplines() if crisis else [],
    })


@patient_bp.route('/api/save-assessment', methods=['POST'])
@login_required
@patient_required
def api_save_assessment():
    from ai.scoring import ScoreError, canonical_type, score_assessment
    from utils.crisis import record_crisis
    from utils.helplines import get_helplines, helplines_lines
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON'}), 400

    user_id = session['user_id']
    data = request.get_json(silent=True) or {}
    key = idem.get_key()
    first = idem.existing(Assessment, user_id, key)
    if first:  # replay: same body as the first answer, no second row, no second AI call
        return _assessment_replay(first)
    assessment_type = canonical_type(data.get('assessment_type'))
    responses = data.get('responses')
    try:  # the score is always recomputed here; any client-sent score is ignored
        result = score_assessment(assessment_type, responses)
    except ScoreError:
        return jsonify({'success': False, 'message': 'Invalid assessment type or responses.'}), 400
    score = result['total']
    contextual = data.get('contextual_responses')
    contextual = contextual if isinstance(contextual, dict) else {}

    crisis_reason = ('phq9_item9_positive' if result.get('item9_positive')
                     else f"{assessment_type.lower().replace('-', '')}_severe" if result['severe'] else None)
    if crisis_reason:  # no model-written advice for a possible crisis: fixed supportive text and helplines
        ai_insights = {
            'summary': f"Your {assessment_type} score is {score} ({result['band']}). This is a screening result, "
                       "not a diagnosis. Please talk to someone you trust and consider contacting a helpline or a clinician soon.",
            'recommendations': ['Reach out to a counselor or doctor in the next few days',
                                'Tell a trusted friend or family member how you are feeling'],
            'resources': helplines_lines(),
        }
        ai_ok = False
    else:
        try:
            ok, ai_insights = run_capped(ai_service.generate_assessment_insights, assessment_type=assessment_type,
                                         score=score, responses=responses, seconds=AI_REQUEST_CAP)
            if not ok or not isinstance(ai_insights, dict):
                raise RuntimeError('ai unavailable')
            ai_ok = True
        except Exception:
            ai_ok = False
            ai_insights = {'summary': 'AI insights are currently unavailable. Please try again later.',
                           'recommendations': [], 'resources': helplines_lines()}

    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found. Please log in again.'}), 400
        assessment = Assessment(user_id=user_id, assessment_type=assessment_type, score=score,
                                responses=responses, contextual_responses=contextual,
                                ai_insights=json.dumps(ai_insights), client_request_id=key)
        db.session.add(assessment)
        user.last_assessment_at = utcnow()
        if crisis_reason:  # O-01: the crisis event and its alert job commit WITH the assessment (all or nothing)
            record_crisis(user_id, 'phq9', 9 if result.get('item9_positive') else 7, crisis_reason)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        first = idem.existing(Assessment, user_id, key) if isinstance(exc, IntegrityError) else None
        if first:  # concurrent double submit: the other request won; answer with its row
            return _assessment_replay(first)
        logger.error("Failed to save assessment user=%s crisis=%s err=%s", user_id, bool(crisis_reason), type(exc).__name__)
        fail = {'success': False, 'message': 'Failed to save assessment.'}
        if crisis_reason:  # the emergency text and helplines never depend on the DB write
            fail.update(crisis=True, ai_insights=ai_insights, helplines=get_helplines())
        return jsonify(fail), 500

    # no points or streaks for assessments (policy: never reward scores)
    return jsonify({
        'success': True,
        'message': 'Assessment saved successfully',
        'assessment_id': assessment.id,
        'score': score,
        'band': result['band'],
        'ai_insights': ai_insights,
        'ai_insights_generated': ai_ok,
        'crisis': bool(crisis_reason),
        'helplines': get_helplines() if crisis_reason else [],
    })
