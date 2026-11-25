"""Goal CRUD: the form-based page and the JSON API used by the dashboard widgets."""
import logging
from datetime import datetime
from flask import render_template, session, redirect, url_for, flash, request, jsonify
from sqlalchemy.exc import IntegrityError

from core.extensions import db
from models import Goal
from core.decorators import patient_required, login_required
from utils import idempotency as idem
from utils.gamification import award_points
from utils.timeutil import ist_today
from utils.pagination import paginate

from . import patient_bp


@patient_bp.route('/goals', methods=['GET', 'POST'])
@login_required
@patient_required
def goals():
    user_id = session['user_id']

    if request.method == 'POST':
        key = idem.get_key()
        title = request.form.get('title')
        description = request.form.get('description', '')
        category = request.form.get('category', 'mental_health')
        priority = request.form.get('priority', 'medium')
        priority = priority if priority in ('low', 'medium', 'high') else 'medium'
        target_value = request.form.get('target_value')
        unit = request.form.get('unit', '')
        target_date = request.form.get('target_date')

        if idem.existing(Goal, user_id, key):  # replay: already created
            flash('Goal created successfully!', 'success')
        elif not title:
            flash('Goal title is required.', 'error')
        else:
            try:
                parsed_target_date = None
                if target_date:
                    parsed_target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

                new_goal = Goal(
                    user_id=user_id,
                    title=title,
                    description=description,
                    category=category,
                    priority=priority,
                    status='active',
                    target_value=float(target_value) if target_value and target_value.strip() else None,
                    current_value=0.0,
                    unit=unit,
                    target_date=parsed_target_date,
                    start_date=ist_today(),
                    client_request_id=key
                )
                if new_goal.target_value is not None and not new_goal.target_value >= 0:
                    raise ValueError('negative target')
                db.session.add(new_goal)
                db.session.commit()
                flash('Goal created successfully!', 'success')
            except ValueError:
                db.session.rollback()
                flash('Target value must be a number and the date must be valid.', 'error')
            except Exception as e:
                db.session.rollback()
                if isinstance(e, IntegrityError) and idem.existing(Goal, user_id, key):  # concurrent double submit
                    flash('Goal created successfully!', 'success')
                else:
                    flash('Failed to create goal.', 'error')
        return redirect(url_for('patient.goals'))

    goals = Goal.query.filter_by(user_id=user_id).all()
    return render_template('goals.html', user_name=session['user_name'], goals=goals)


@patient_bp.route('/api/goals', methods=['GET', 'POST'])
@patient_required
def handle_goals():
    """Handle goal creation and updates."""
    user_id = session['user_id']

    if request.method == 'POST':
        key = None
        try:
            data = request.get_json(silent=True) or {}
            title = data.get('title')
            description = data.get('description')
            category = data.get('category') or 'mental_health'
            target_value = data.get('target_value')
            unit = data.get('unit')
            priority = data.get('priority') or 'medium'
            priority = priority if priority in ('low', 'medium', 'high') else 'medium'
            target_date = data.get('target_date')
            key = idem.get_key()
            first = idem.existing(Goal, user_id, key)
            if first:  # replay: the goal already exists
                return jsonify({'success': True, 'message': 'Goal created successfully!',
                                'goal': {'id': first.id, 'title': first.title, 'description': first.description}})

            if not title:
                return jsonify({'success': False, 'message': 'Title is required.'}), 400

            try:
                target_value = float(target_value) if target_value not in (None, '') else None
                parsed_target_date = datetime.strptime(target_date, '%Y-%m-%d').date() if target_date else None
                if target_value is not None and not target_value >= 0:
                    raise ValueError('negative target')
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'Target value must be a number and the date YYYY-MM-DD.'}), 400

            new_goal = Goal(
                client_request_id=key,
                user_id=user_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                target_value=target_value,
                unit=unit,
                target_date=parsed_target_date,
                start_date=ist_today()
            )
            db.session.add(new_goal)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Goal created successfully!',
                'goal': {
                    'id': new_goal.id,
                    'title': new_goal.title,
                    'description': new_goal.description
                }
            }), 201
        except idem.InvalidKey:
            raise
        except Exception as e:
            db.session.rollback()
            first = idem.existing(Goal, user_id, key) if isinstance(e, IntegrityError) else None
            if first:  # concurrent double submit: the other request created it
                return jsonify({'success': True, 'message': 'Goal created successfully!',
                                'goal': {'id': first.id, 'title': first.title, 'description': first.description}})
            logging.getLogger(__name__).error("Error adding goal for user %s: %s", user_id, type(e).__name__)
            return jsonify({'success': False, 'message': 'Failed to create goal.'}), 500

    # GET request logic
    # default page 100: the goals page has no paging UI yet; `meta` says when there are more
    goals, goals_meta = paginate(Goal.query.filter_by(user_id=user_id).order_by(Goal.created_at.desc(), Goal.id.desc()), default=100)
    goals_data = []
    for goal in goals:
        goals_data.append({
            'id': goal.id,
            'title': goal.title,
            'description': goal.description,
            'category': goal.category,
            'status': goal.status,
            'priority': goal.priority,
            'target_value': goal.target_value,
            'current_value': goal.current_value,
            'unit': goal.unit,
            'target_date': goal.target_date.strftime('%Y-%m-%d') if goal.target_date else None,
            'progress_percentage': goal.progress_percentage,
            'created_at': goal.created_at.strftime('%Y-%m-%d') if goal.created_at else None
        })
    return jsonify({'success': True, 'goals': goals_data, 'meta': goals_meta})


@patient_bp.route('/api/goals/<int:goal_id>', methods=['PUT', 'DELETE'])
@patient_required
def handle_goal(goal_id):
    logger = logging.getLogger(__name__)
    user_id = session['user_id']
    goal = Goal.query.filter_by(id=goal_id, user_id=user_id).first()

    if not goal:
        return jsonify({'success': False, 'message': 'Goal not found.'}), 404

    if request.method == 'DELETE':
        try:
            db.session.delete(goal)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Goal deleted successfully!'})
        except Exception:
            db.session.rollback()
            logger.exception('goal delete failed')
            return jsonify({'success': False, 'message': 'Could not delete the goal.'}), 500

    elif request.method == 'PUT':
        data = request.get_json(silent=True) or {}

        try:
            for field in ('target_value', 'current_value'):
                if field in data:
                    setattr(goal, field, float(data[field]) if data[field] not in (None, '') else None)
        except (TypeError, ValueError):
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Values must be numbers.'}), 400
        for field in ('title', 'description', 'category', 'priority', 'unit'):
            if field in data:
                setattr(goal, field, data[field])

        # 'completed' (bool) or 'status' change the status; if neither is sent it stays as it is.
        new_status = None
        if 'completed' in data:
            new_status = 'completed' if data['completed'] is True else 'active'
        elif 'status' in data:
            new_status = data['status']
        if new_status is not None and new_status not in ('active', 'completed', 'paused'):
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Invalid status.'}), 400

        try:
            if new_status is not None and new_status != goal.status:
                goal.status = new_status
                goal.completed_date = ist_today() if new_status == 'completed' else None

            goal.updated_at = datetime.utcnow()
            db.session.commit()
            if 'current_value' in data or new_status == 'completed':  # progress or completion, not a title edit
                award_points(user_id, 10, 'goal_progress', ref=f'goal:{goal.id}:{ist_today().isoformat()}')  # once per goal per day

            return jsonify({
                'success': True,
                'message': 'Goal updated successfully!',
                'goal': {
                    'id': goal.id,
                    'title': goal.title,
                    'description': goal.description,
                    'category': goal.category,
                    'status': goal.status,
                    'priority': goal.priority,
                    'progress_percentage': goal.progress_percentage
                }
            })
        except Exception:
            db.session.rollback()
            logger.exception('goal update failed')
            return jsonify({'success': False, 'message': 'Could not update the goal.'}), 500
