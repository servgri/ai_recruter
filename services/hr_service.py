"""HR service for managing contests, tasks, and criteria."""

from flask import Blueprint, request, jsonify
from typing import Dict, List, Optional
from utils.database import Database

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')


@hr_bp.route('/contests', methods=['GET'])
def get_contests():
    """Get all contests."""
    try:
        db = Database()
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        contests = db.get_all_contests(active_only=active_only)
        return jsonify({
            'status': 'success',
            'contests': contests
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>', methods=['GET'])
def get_contest(contest_id: int):
    """Get contest by ID with full data."""
    try:
        db = Database()
        contest = db.get_full_contest_data(contest_id)
        if not contest:
            return jsonify({
                'status': 'error',
                'error': 'Contest not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'contest': contest
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests', methods=['POST'])
def create_contest():
    """Create a new contest."""
    try:
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        is_active = data.get('is_active', 1)
        
        if not name:
            return jsonify({
                'status': 'error',
                'error': 'Contest name is required'
            }), 400
        
        db = Database()
        contest_id = db.create_contest(name, description, is_active)
        
        if contest_id:
            return jsonify({
                'status': 'success',
                'contest_id': contest_id,
                'message': 'Contest created successfully'
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'error': 'Failed to create contest'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>', methods=['PUT'])
def update_contest(contest_id: int):
    """Update contest."""
    try:
        data = request.get_json() or {}
        name = data.get('name')
        description = data.get('description')
        is_active = data.get('is_active')
        
        if name is not None:
            name = name.strip()
            if not name:
                return jsonify({
                    'status': 'error',
                    'error': 'Contest name cannot be empty'
                }), 400
        
        db = Database()
        success = db.update_contest(contest_id, name, description, is_active)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Contest updated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'error': 'Contest not found or update failed'
            }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>', methods=['DELETE'])
def delete_contest(contest_id: int):
    """Delete contest."""
    try:
        db = Database()
        success = db.delete_contest(contest_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Contest deleted successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'error': 'Contest not found'
            }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/tasks', methods=['GET'])
def get_contest_tasks(contest_id: int):
    """Get all tasks for a contest."""
    try:
        db = Database()
        tasks = db.get_contest_tasks(contest_id)
        
        # Add criteria to each task
        for task in tasks:
            task['criteria'] = db.get_task_criteria(contest_id, task['task_number'])
        
        return jsonify({
            'status': 'success',
            'tasks': tasks
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/tasks', methods=['POST'])
def create_contest_task(contest_id: int):
    """Create or update a task for a contest."""
    try:
        data = request.get_json() or {}
        task_number = data.get('task_number')
        task_text = data.get('task_text', '').strip()
        reference_answer = data.get('reference_answer', '').strip()
        
        if task_number is None:
            return jsonify({
                'status': 'error',
                'error': 'task_number is required'
            }), 400
        
        if not isinstance(task_number, int) or task_number < 1 or task_number > 4:
            return jsonify({
                'status': 'error',
                'error': 'task_number must be between 1 and 4'
            }), 400
        
        if not task_text:
            return jsonify({
                'status': 'error',
                'error': 'task_text is required'
            }), 400
        
        db = Database()
        task_id = db.create_contest_task(contest_id, task_number, task_text, reference_answer)
        
        if task_id:
            return jsonify({
                'status': 'success',
                'task_id': task_id,
                'message': 'Task created/updated successfully'
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'error': 'Failed to create task'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/tasks/<int:task_number>', methods=['PUT'])
def update_contest_task(contest_id: int, task_number: int):
    """Update contest task."""
    try:
        data = request.get_json() or {}
        task_text = data.get('task_text')
        reference_answer = data.get('reference_answer')
        
        if task_text is not None:
            task_text = task_text.strip()
            if not task_text:
                return jsonify({
                    'status': 'error',
                    'error': 'task_text cannot be empty'
                }), 400
        
        db = Database()
        success = db.update_contest_task(contest_id, task_number, task_text, reference_answer)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Task updated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'error': 'Task not found or update failed'
            }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/tasks/<int:task_number>', methods=['DELETE'])
def delete_contest_task(contest_id: int, task_number: int):
    """Delete contest task."""
    try:
        db = Database()
        success = db.delete_contest_task(contest_id, task_number)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Task deleted successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'error': 'Task not found'
            }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/tasks/<int:task_number>/criteria', methods=['GET'])
def get_task_criteria(contest_id: int, task_number: int):
    """Get all criteria for a task."""
    try:
        db = Database()
        criteria = db.get_task_criteria(contest_id, task_number)
        return jsonify({
            'status': 'success',
            'criteria': criteria
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/tasks/<int:task_number>/criteria', methods=['POST'])
def create_task_criterion(contest_id: int, task_number: int):
    """Create or update a criterion for a task."""
    try:
        data = request.get_json() or {}
        criterion_number = data.get('criterion_number')
        criterion_text = data.get('criterion_text', '').strip()
        weight = data.get('weight', 1.0)
        
        if criterion_number is None:
            return jsonify({
                'status': 'error',
                'error': 'criterion_number is required'
            }), 400
        
        if not isinstance(criterion_number, int) or criterion_number < 1:
            return jsonify({
                'status': 'error',
                'error': 'criterion_number must be a positive integer'
            }), 400
        
        if not criterion_text:
            return jsonify({
                'status': 'error',
                'error': 'criterion_text is required'
            }), 400
        
        try:
            weight = float(weight)
            if weight < 0:
                weight = 1.0
        except (ValueError, TypeError):
            weight = 1.0
        
        db = Database()
        criterion_id = db.create_task_criterion(contest_id, task_number, criterion_number, criterion_text, weight)
        
        if criterion_id:
            return jsonify({
                'status': 'success',
                'criterion_id': criterion_id,
                'message': 'Criterion created/updated successfully'
            }), 201
        else:
            return jsonify({
                'status': 'error',
                'error': 'Failed to create criterion'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/tasks/<int:task_number>/criteria/<int:criterion_number>', methods=['PUT'])
def update_task_criterion(contest_id: int, task_number: int, criterion_number: int):
    """Update task criterion."""
    try:
        data = request.get_json() or {}
        criterion_text = data.get('criterion_text')
        weight = data.get('weight')
        
        if criterion_text is not None:
            criterion_text = criterion_text.strip()
            if not criterion_text:
                return jsonify({
                    'status': 'error',
                    'error': 'criterion_text cannot be empty'
                }), 400
        
        if weight is not None:
            try:
                weight = float(weight)
                if weight < 0:
                    return jsonify({
                        'status': 'error',
                        'error': 'weight must be non-negative'
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    'status': 'error',
                    'error': 'weight must be a number'
                }), 400
        
        db = Database()
        success = db.update_task_criterion(contest_id, task_number, criterion_number, criterion_text, weight)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Criterion updated successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'error': 'Criterion not found or update failed'
            }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/tasks/<int:task_number>/criteria/<int:criterion_number>', methods=['DELETE'])
def delete_task_criterion(contest_id: int, task_number: int, criterion_number: int):
    """Delete task criterion."""
    try:
        db = Database()
        success = db.delete_task_criterion(contest_id, task_number, criterion_number)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Criterion deleted successfully'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'error': 'Criterion not found'
            }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@hr_bp.route('/contests/<int:contest_id>/save-all', methods=['POST'])
def save_contest_all(contest_id: int):
    """Save entire contest with all tasks and criteria in one request."""
    try:
        data = request.get_json() or {}
        name = data.get('name')
        description = data.get('description')
        is_active = data.get('is_active')
        tasks = data.get('tasks', {})  # {task_number: {task_text, reference_answer, criteria: [...]}}
        
        db = Database()
        
        # Update contest info if provided
        if name is not None or description is not None or is_active is not None:
            db.update_contest(contest_id, name, description, is_active)
        
        # Save tasks and criteria
        for task_number_str, task_data in tasks.items():
            try:
                task_number = int(task_number_str)
                if task_number < 1 or task_number > 4:
                    continue
                
                task_text = task_data.get('task_text', '').strip()
                reference_answer = task_data.get('reference_answer', '').strip()
                criteria = task_data.get('criteria', [])
                
                if task_text:
                    # Create/update task
                    db.create_contest_task(contest_id, task_number, task_text, reference_answer)
                    
                    # Delete existing criteria for this task
                    existing_criteria = db.get_task_criteria(contest_id, task_number)
                    for crit in existing_criteria:
                        db.delete_task_criterion(contest_id, task_number, crit['criterion_number'])
                    
                    # Create new criteria
                    for crit_data in criteria:
                        criterion_number = crit_data.get('criterion_number')
                        criterion_text = crit_data.get('criterion_text', '').strip()
                        weight = crit_data.get('weight', 1.0)
                        
                        if criterion_number and criterion_text:
                            try:
                                weight = float(weight) if weight is not None else 1.0
                                db.create_task_criterion(contest_id, task_number, criterion_number, criterion_text, weight)
                            except (ValueError, TypeError):
                                pass
            except (ValueError, TypeError):
                continue
        
        return jsonify({
            'status': 'success',
            'message': 'Contest saved successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
