from collections import defaultdict

from flask import Blueprint, request, jsonify
from app import db
from app.models import ShiftAssigned, Shift, Employee
from datetime import datetime

shifts_bp = Blueprint('shifts', __name__)

@shifts_bp.route('/calendar', methods=['GET'])
def get_calendar_matrix():
    # 1. Parse and validate the query parameters tracking timeline boundaries
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify({"error": "Missing required start_date or end_date parameters."}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # 2. Query flat database junction row records stretching across the date range
    assignments = db.session.query(ShiftAssigned, Shift, Employee).\
        join(Shift, ShiftAssigned.shift_id == Shift.id).\
        join(Employee, ShiftAssigned.employee_id == Employee.id).\
        filter(ShiftAssigned.assigned_date.between(start_date, end_date)).all()

    # 3. Use an intermediate nested dictionary matrix to group records by date and shift
    # Structure: matrix[date_str][shift_name] = { "note": str, "employees": [...] }
    calendar_matrix = defaultdict(dict)

    for assoc, shift, employee in assignments:
        date_key = assoc.assigned_date.strftime('%Y-%m-%d')
        shift_key = shift.shift_name # e.g., 'morning', 'afternoon', 'evening', 'night'

        if shift_key not in calendar_matrix[date_key]:
            # Derive elegant localized titles and display intervals safely
            display_title = f"Shift {shift_key.capitalize()}"
            if shift_key == "morning": display_title = "Morning Shift"
            elif shift_key == "afternoon": display_title = "Afternoon Shift"
            elif shift_key == "evening": display_title = "Evening Shift"
            elif shift_key == "night": display_title = "Night Shift"

            calendar_matrix[date_key][shift_key] = {
                "type": shift_key,
                "title": display_title,
                "time": f"{shift.start_time.strftime('%H:%M')} - {shift.end_time.strftime('%H:%M')}",
                "note": assoc.note or "",
                "employees": []
            }

        # Append structured sub-object tracking metrics matching Employee model parameters
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
    data = request.json or {}
    date_str = data.get('date')
    shift_type = data.get('shift_type')
    employee_id = data.get('employee_id')
    note_text = data.get('note', '')

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
        note=note_text
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
    data = request.json or {}
    date_str = data.get('date')
    shift_type = data.get('shift_type')
    new_note = data.get('note', '')

    if not all([date_str, shift_type]):
        return jsonify({"error": "Missing coordinates needed to target shift note"}), 400

    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    shift_def = Shift.query.filter_by(shift_name=shift_type).first()
    if not shift_def:
        return jsonify({"error": "Invalid shift type parameter"}), 404

    # Fetch all flat employee rows tracking this shared shift slot container code block
    matching_assignments = ShiftAssigned.query.filter_by(
        assigned_date=target_date,
        shift_id=shift_def.id
    ).all()

    try:
        # Uniformly propagate modified notes string data across all active team records
        for assignment in matching_assignments:
            assignment.note = new_note
        
        db.session.commit()
        return jsonify({"success": True, "message": "Shift operational note synchronized successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database bulk-sync update exception: {str(e)}"}), 500