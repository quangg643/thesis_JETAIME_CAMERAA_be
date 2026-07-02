from collections import defaultdict

from flask import Blueprint, request, jsonify
from app import db
from app.helpers import verify_shift_is_editable
from app.models import DailyShiftStatus, ShiftAssigned, Shift, Employee
from datetime import datetime

shifts_bp = Blueprint('shifts', __name__)

@shifts_bp.route('/calendar', methods=['GET'])
def get_calendar_matrix():
    """
    Compile a complete date-bounded grid matrix mapping shift types to employee assignments
    ---
    tags:
      - Shift Schedules
    parameters:
      - name: start_date
        in: query
        type: string
        required: true
        description: Format YYYY-MM-DD
      - name: end_date
        in: query
        type: string
        required: true
        description: Format YYYY-MM-DD
      - name: query
        in: query
        type: string
        description: Optional keyword search token matching employee name
    responses:
      200:
        description: Calendar matrix layout categorized by ISO Date strings and shift name rows
        schema:
          type: object
          additionalProperties:
            type: object
            additionalProperties:
              type: object
              properties:
                note: {type: string, example: "Delays expected due to bad weather"}
                staff:
                  type: array
                  items:
                    type: object
                    properties:
                      id: {type: integer}
                      name: {type: string}
                      email: {type: string}
      400:
        description: Missing bounds or malformed date schemas
    """
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    search_query = request.args.get('query', '').strip().lower() # Capture search token optional parameters

    if not start_date_str or not end_date_str:
        return jsonify({"error": "Missing required start_date or end_date parameters."}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Query flat database junction row records stretching across the date range
    assignments = db.session.query(ShiftAssigned, Shift, Employee).\
        join(Shift, ShiftAssigned.shift_id == Shift.id).\
        join(Employee, ShiftAssigned.employee_id == Employee.id).\
        filter(ShiftAssigned.assigned_date.between(start_date, end_date)).all()

    daily_statuses = DailyShiftStatus.query.filter(
        DailyShiftStatus.assigned_date.between(start_date, end_date)
    ).all()
    
    status_map = {(status.assigned_date.strftime('%Y-%m-%d'), status.shift_id): status.note for status in daily_statuses}

    calendar_matrix = defaultdict(dict)

    # Pre-populate rows with notes (Only skip if actively filtering for a specific employee match)
    if not search_query:
        for (date_val, shift_id), note_text in status_map.items():
            shift = Shift.query.get(shift_id)
            if shift:
                shift_key = shift.shift_name
                calendar_matrix[date_val][shift_key] = {
                    "type": shift_key,
                    "title": f"Shift {shift_key.capitalize()}",
                    "time": f"{shift.start_time.strftime('%H:%M')} - {shift.end_time.strftime('%H:%M')}",
                    "note": note_text or "",
                    "employees": []
                }

    # Now merge in the assigned employees
    for assoc, shift, employee in assignments:
        # Optimization check: If searching by employee, drop rows where name doesn't match token parameters
        if search_query and search_query not in employee.name.lower():
            continue

        date_key = assoc.assigned_date.strftime('%Y-%m-%d')
        shift_key = shift.shift_name

        if shift_key not in calendar_matrix[date_key]:
            calendar_matrix[date_key][shift_key] = {
                "type": shift_key,
                "title": f"Shift {shift_key.capitalize()}",
                "time": f"{shift.start_time.strftime('%H:%M')} - {shift.end_time.strftime('%H:%M')}",
                "note": status_map.get((date_key, shift.id), ""),
                "employees": []
            }

        calendar_matrix[date_key][shift_key]["employees"].append({
            "id": employee.id,
            "name": employee.name,
            "email": employee.email,
            "phone": employee.phone or "N/A"
        })

    return jsonify(calendar_matrix)

# ==========================================================================
# 1. API CONTROLLER: UNASSIGN STAFF ROUTE
# ==========================================================================
@shifts_bp.route('/unassign', methods=['POST'])
def unassign_employee():
    """
    Remove an employee assignment from a shift date
    ---
    tags:
      - Shift Schedules
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - date
            - shift_type
            - employee_id
          properties:
            date: {type: string, example: "2026-07-01", description: "Format: YYYY-MM-DD"}
            shift_type: {type: string, example: "Morning"}
            employee_id: {type: integer, example: 5}
    responses:
      200:
        description: Employee assignment successfully removed
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "Assignment successfully removed."}
      400:
        description: Invalid date format
      403:
        description: Cannot modify past or locked rosters
        schema:
          type: object
          properties:
            success: {type: boolean, example: false}
            error: {type: string, example: "This shift assignment is locked and cannot be edited."}
      404:
        description: Shift assignment record not found
    """
    data = request.json or {}
    date_str = data.get('date')
    shift_type = data.get('shift_type')  # e.g., 'morning', 'evening'
    employee_id = data.get('employee_id')

    if not all([date_str, shift_type, employee_id]):
        return jsonify({"error": "Missing required payload tracking parameters"}), 400

    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    shift_def = Shift.query.filter_by(shift_name=shift_type).first()
    if not shift_def:
        return jsonify({"error": "Target shift type definition not found"}), 404

    # Enforce Unique Constraint removal parameters row search logic safely
    assignment = ShiftAssigned.query.filter_by(
        assigned_date=target_date,
        shift_id=shift_def.id,
        employee_id=int(employee_id)
    ).first()

    if not assignment:
        return jsonify({"error": "No matching shift assignment record located"}), 404

    try:
        db.session.delete(assignment)
        db.session.commit()
        return jsonify({"success": True, "message": "Employee unassigned successfully from shift"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database exception occurred: {str(e)}"}), 500


# ==========================================================================
# 2. API CONTROLLER: ASSIGN STAFF ROUTE
# ==========================================================================
@shifts_bp.route('/assign', methods=['POST'])
def assign_employee():
    """
    Assign an employee to a specific shift date
    ---
    tags:
      - Shift Schedules
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - date
            - shift_type
            - employee_id
          properties:
            date: {type: string, example: "2026-07-01", description: "Format: YYYY-MM-DD"}
            shift_type: {type: string, example: "Morning", description: "The unique shift name identifier"}
            employee_id: {type: integer, example: 5}
    responses:
      200:
        description: Employee successfully assigned to the shift
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "Employee successfully assigned."}
      400:
        description: Invalid request parameters or malformed date format
        schema:
          type: object
          properties:
            error: {type: string, example: "Invalid date format. Use YYYY-MM-DD"}
      403:
        description: Operation forbidden because the shift is locked or in the past
        schema:
          type: object
          properties:
            success: {type: boolean, example: false}
            error: {type: string, example: "This shift assignment is locked and cannot be edited."}
      404:
        description: Shift type or Employee record not found
        schema:
          type: object
          properties:
            error: {type: string, example: "Invalid shift type parameter"}
    """
    data = request.json or {}
    date_str = data.get('date')
    shift_type = data.get('shift_type')
    employee_id = data.get('employee_id')

    if not all([date_str, shift_type, employee_id]):
        return jsonify({"error": "Missing parameters needed to initialize assignment"}), 400

    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    shift_def = Shift.query.filter_by(shift_name=shift_type).first()
    employee = Employee.query.get(int(employee_id))

    if not shift_def or not employee:
        return jsonify({"error": "Employee profile or Shift structural definition not found"}), 404

    # Enforce database unique constraint row rules early before posting inserts
    existing = ShiftAssigned.query.filter_by(
        employee_id=employee.id,
        shift_id=shift_def.id,
        assigned_date=target_date
    ).first()

    if existing:
        return jsonify({"error": "This employee is already assigned to this specific tracking slot"}), 400

    new_assignment = ShiftAssigned(
        employee_id=employee.id,
        shift_id=shift_def.id,
        assigned_date=target_date,
    )

    try:
        db.session.add(new_assignment)
        db.session.commit()
        return jsonify({
            "success": True,
            "employee_email": employee.email,
            "employee_phone": employee.phone or "N/A"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database write exception: {str(e)}"}), 500


# ==========================================================================
# 3. API CONTROLLER: BULK UPDATE SHIFT NOTES ROUTE
# ==========================================================================
@shifts_bp.route('/update-note', methods=['POST'])
def update_shift_note():
    """
    Create or update an administrative note for a specific shift date
    ---
    tags:
      - Shift Schedules
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - date
            - shift_type
            - note
          properties:
            date: {type: string, example: "2026-07-01", description: "Format: YYYY-MM-DD"}
            shift_type: {type: string, example: "Morning"}
            note: {type: string, example: "Delays expected due to bad weather"}
    responses:
      200:
        description: Shift annotation note successfully updated
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "Shift note updated successfully."}
      400:
        description: Missing note string values or invalid parameters
      403:
        description: Timeframe locked; historical shift notes are read-only
        schema:
          type: object
          properties:
            success: {type: boolean, example: false}
            error: {type: string, example: "This shift assignment is locked and cannot be edited."}
      404:
        description: Specified shift configuration not found
    """
    data = request.json or {}
    date_str = data.get('date')
    shift_type = data.get('shift_type')
    new_note = data.get('note', '')

    if not all([date_str, shift_type]):
        return jsonify({"error": "Missing coordinates needed to target shift note"}), 400
    
    is_editable, error_msg = verify_shift_is_editable(date_str, shift_type)
    if not is_editable:
        return jsonify({"success": False, "error": error_msg}), 403

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    shift_def = Shift.query.filter_by(shift_name=shift_type).first()
    if not shift_def:
        return jsonify({"error": "Invalid shift type parameter"}), 404

    try:
        # Check if a global daily status row already exists for this shift on this date
        daily_status = DailyShiftStatus.query.filter_by(
            assigned_date=target_date,
            shift_id=shift_def.id
        ).first()

        if daily_status:
            # If it exists, update the note text string
            daily_status.note = new_note
        else:
            # If it doesn't exist, build a fresh row record container
            daily_status = DailyShiftStatus(
                assigned_date=target_date,
                shift_id=shift_def.id,
                note=new_note
            )
            db.session.add(daily_status)
        
        db.session.commit()
        return jsonify({"success": True, "message": "Shift operational note synchronized successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500