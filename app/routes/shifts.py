from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.decorators import role_required
from app.enums import UserRole
from app.helpers import get_vietnam_time
from app.models import Employee, Kpi, Shift, ShiftAssigned
from app import db

shifts_bp = Blueprint('shifts', __name__)

@shifts_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_shifts():
    """
    Get all defined shift templates
    ---
    tags:
      - Shifts
    security:
      - cookieAuth: []
    responses:
      200:
        description: List of all shifts (e.g., Morning, Evening)
        schema:
          properties:
            success: {type: boolean}
            total: {type: integer}
            shifts:
              type: array
              items:
                properties:
                  id: {type: integer}
                  start_time: {type: string, example: "08:00:00"}
                  end_time: {type: string, example: "16:00:00"}
                  hours: {type: number}
    """
    try:
        shifts = Shift.query.all()
        
        shifts_list = []
        for shift in shifts:
            shifts_list.append({
                'id': shift.id,
                'start_time': shift.start_time.strftime('%H:%M:%S') if shift.start_time else None,
                'end_time': shift.end_time.strftime('%H:%M:%S') if shift.end_time else None,
                'hours': shift.hours
            })
        
        return jsonify({
            'success': True,
            'total': len(shifts_list),
            'shifts': shifts_list
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Error fetching shifts',
            'error': str(e)
        }), 500
    
@shifts_bp.route('/employees', methods=['GET'])
@jwt_required()
def get_assigned_shift():
    """
    Get shift assignments for the logged-in employee
    ---
    tags:
      - Shifts
    security:
      - cookieAuth: []
    responses:
      200:
        description: List of assignments with detailed shift info
        schema:
          properties:
            success: {type: boolean}
            data:
              type: array
              items:
                properties:
                  assignment_id: {type: integer}
                  assigned_at: {type: string, format: date-time}
                  shift:
                    type: object
                    properties:
                      id: {type: integer}
                      start_time: {type: string}
                      end_time: {type: string}
    """
    try:
        current_employee_id = get_jwt_identity()

        assignments = ShiftAssigned.query.filter_by(employee_id=current_employee_id)\
                                        .order_by(ShiftAssigned.created_at.desc())\
                                        .all()

        shifts_list = []
        for assignment in assignments:
            shift = assignment.shift 

            shifts_list.append({
                "assignment_id": assignment.id,
                "assigned_at": assignment.created_at.isoformat() if assignment.created_at else None,
                "shift": {
                    "id": shift.id,
                    "start_time": shift.start_time.strftime("%H:%M") if shift.start_time else None,
                    "end_time": shift.end_time.strftime("%H:%M") if shift.end_time else None,
                    "hours": shift.hours,
                }
            })

        return jsonify({
            "success": True,
            "total": len(shifts_list),
            "data": shifts_list
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Failed to fetch assigned shifts",
            "error": str(e)
        }), 500
    
@shifts_bp.route('/employee/unassign', methods=['DELETE'])
@role_required(UserRole.MANAGER)
def change_or_remove_assigned_shift():
    """
    Remove an employee's shift assignment (Manager only)
    ---
    tags:
      - Shifts
    security:
      - cookieAuth: []
    description: >
      Constraints:
      1. Cannot delete shifts for today or the past.
      2. Cannot delete if the employee has already recorded customer interactions (KPIs) for that shift.
    parameters:
      - name: assignment_id
        in: query
        type: integer
        required: true
    responses:
      200:
        description: Shift assignment removed successfully
      400:
        description: Cannot delete due to recorded KPIs
      403:
        description: Cannot modify past or current date shifts
      404:
        description: Assignment not found
    """
    try:
        current_employee_id = get_jwt_identity()

        assignment_id = request.args.get('assignment_id')
        vn_now = get_vietnam_time()
        today_date = vn_now.date()

        if not assignment_id:
            return jsonify({
                "success": False,
                "message": "assignment_id is required"
            }), 400

        assignment = ShiftAssigned.query.filter_by(
            id=assignment_id,
            employee_id=current_employee_id
        ).first()

        if not assignment:
            return jsonify({
                "success": False,
                "message": "Assignment not found or you don't have permission to modify it"
            }), 404
        
        if assignment.assigned_date <= today_date:
            return jsonify({
                "success": False, 
                "message": "Cannot modify or delete shifts for today or past dates. Contact your manager."
            }), 403
        
        kpi_exists = Kpi.query.filter_by(
            employee_id=current_employee_id,
            shift_assigned_id=assignment.shift_id,
            created_at=assignment.assigned_date
        ).first()

        if kpi_exists and kpi_exists.no_customer > 0:
            return jsonify({
                "success": False,
                "message": "Cannot delete shift: You have already recorded customers during this period."
            }), 400

  
        db.session.delete(assignment)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Shift assignment removed successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Failed to process request",
            "error": str(e)
        }), 500

@shifts_bp.route('/assign', methods=['POST'])
@role_required(UserRole.MANAGER)
def manager_assign_shift():
    """
    Assign a shift to an employee (Manager only)
    ---
    tags:
      - Shifts
    security:
      - cookieAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - employee_id
            - shift_id
            - assigned_date
          properties:
            employee_id: {type: integer}
            shift_id: {type: integer}
            assigned_date: {type: string, format: date, example: "2026-05-01"}
    responses:
      201:
        description: Shift assigned successfully
      400:
        description: Missing fields or invalid date format
      409:
        description: Employee is already assigned to this shift on this date
    """
    try:
        data = request.get_json()
        target_employee_id = data.get('employee_id')
        shift_id = data.get('shift_id')
        assigned_date_str = data.get('assigned_date')

        if not all([target_employee_id, shift_id, assigned_date_str]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        # 1. Fetch the actual objects (Validates existence)
        target_employee = Employee.query.get_or_404(target_employee_id)
        target_shift = Shift.query.get_or_404(shift_id)


        # 2. Date conversion
        try:
            assigned_date = datetime.strptime(assigned_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format (YYYY-MM-DD)"}), 400

        # 3. Check for duplicate assignment using IDs (fastest check)
        is_already_assigned = ShiftAssigned.query.filter_by(
            employee_id=target_employee_id,
            shift_id=shift_id,
            assigned_date=assigned_date
        ).first()

        if is_already_assigned:
            return jsonify({
                "success": False, 
                "message": f"{target_employee.name} is already assigned to this shift on this date"
            }), 409

        # 4. Create assignment using the objects
        # SQLAlchemy handles the ID mapping internally
        new_assignment = ShiftAssigned(
            employee=target_employee,
            shift=target_shift,
            assigned_date=assigned_date
        )

        db.session.add(new_assignment)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Shift assigned to {target_employee.name} successfully",
            "data": {
                "assignment_id": new_assignment.id,
                "employee": target_employee.name,
                "date": str(new_assignment.assigned_date)
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500