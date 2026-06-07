from flask import Blueprint, request, jsonify
from app import db
from app.models import Employee, Penalty
from app.enums import PenaltyLevel
from app.helpers import get_vietnam_time

# Registered blueprint routing channel
penalties_bp = Blueprint('penalties', __name__)

@penalties_bp.route('/', methods=['POST'])
def log_employee_penalty():
    data = request.get_json() or {}

    employee_id = data.get('employee_id')
    penalty_name = data.get('penalty_name', '').strip()
    raw_level = data.get('level')
    count = data.get('count', 1)

    # 1. Base Structure Validation
    if not employee_id or not penalty_name or raw_level is None:
        return jsonify({"error": "Missing required fields: employee_id, penalty_name, and level are mandatory."}), 400

    # 2. ENUM VALIDATION: Ensure incoming payload matches enum values (1 or 2)
    try:
        penalty_level = PenaltyLevel(int(raw_level))
    except (ValueError, TypeError):
        return jsonify({
            "error": f"Invalid penalty level selector. Must match an integer Enum option: {[e.value for e in PenaltyLevel]}."
        }), 400

    try:
        count = int(count)
        if count <= 0:
            return jsonify({"error": "Count must be a positive integer greater than 0."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid type provided for count attribute."}), 400

    # 3. Target Employee Verification
    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({"error": f"Employee with ID #{employee_id} does not exist."}), 404

    # 4. Save Entry to DB
    new_penalty = Penalty(
        employee_id=employee_id,
        penalty_name=penalty_name,
        level=penalty_level, # Mapped enum class instance variable
        count=count,
        created_at=get_vietnam_time()
    )

    try:
        db.session.add(new_penalty)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database persistence logging issue.", "details": str(e)}), 500

    return jsonify({
        "success": True,
        "message": f"Penalty successfully logged for {employee.name}.",
        "penalty": {
            "id": new_penalty.id,
            "employee_id": new_penalty.employee_id,
            "penalty_name": new_penalty.penalty_name,
            "level": new_penalty.level.value, # Extract the underlying integer (1 or 2)
            "count": new_penalty.count,
            "created_at": new_penalty.created_at.isoformat()
        }
    }), 201