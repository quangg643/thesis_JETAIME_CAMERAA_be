from flask import Blueprint, request, jsonify
from app import db
from app.models import Employee, Penalty
from app.enums import PenaltyLevel
from app.helpers import get_vietnam_time

penalties_bp = Blueprint('penalties', __name__)

@penalties_bp.route('/', methods=['GET'])
def get_all_penalties():
    try:
        # 1. Extract query parameters with defensive fallbacks
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search_query = request.args.get('search', '').strip()

        # Enforce positive integers
        if page < 1: page = 1
        if per_page < 1: per_page = 10

        # 2. Build the base query (Join Penalty and Employee)
        query = db.session.query(Penalty, Employee).join(
            Employee, Penalty.employee_id == Employee.id
        )

        # 3. Apply server-side search filter if query exists
        if search_query:
            query = query.filter(
                (Employee.name.ilike(f"%{search_query}%")) |
                (Penalty.penalty_name.ilike(f"%{search_query}%")) |
                (db.cast(Penalty.employee_id, db.String).ilike(f"%{search_query}%"))
            )
        query = query.order_by(Employee.id.desc())
        
        # 4. Execute SQLAlchemy pagination engine
        paginated_data = query.paginate(page=page, per_page=per_page, error_out=False)
        
        penalties_list = []
        for penalty, employee in paginated_data.items:
            penalties_list.append({
                "id": penalty.id,
                "employee_id": penalty.employee_id,
                "employee_name": employee.name,
                "penalty_name": penalty.penalty_name,
                "level": penalty.level.value if hasattr(penalty.level, 'value') else int(penalty.level),
                "count": penalty.count,
                "created_at": penalty.created_at.isoformat() if penalty.created_at else None
            })
            
        # 5. Return data accompanied by meta-pagination attributes
        return jsonify({
            "data": penalties_list,
            "meta": {
                "current_page": paginated_data.page,
                "per_page": paginated_data.per_page,
                "total_items": paginated_data.total,
                "total_pages": paginated_data.pages,
                "has_next": paginated_data.has_next,
                "has_prev": paginated_data.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": "Failed to retrieve penalty records.", "details": str(e)}), 5

# ==========================================
# 2. DELETE A PENALTY RECORD
# ==========================================
@penalties_bp.route('/<int:penalty_id>', methods=['DELETE'])
def delete_penalty(penalty_id):
    penalty = Penalty.query.get(penalty_id)
    
    if not penalty:
        return jsonify({"error": f"Penalty record #{penalty_id} does not exist."}), 404
        
    try:
        db.session.delete(penalty)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error while deleting record.", "details": str(e)}), 500
        
    return jsonify({
        "success": True,
        "message": f"Penalty record #{penalty_id} successfully deleted."
    }), 200

@penalties_bp.route('/', methods=['POST'])
def log_employee_penalty():
    data = request.get_json() or {}
    employee_id = data.get('employee_id')
    penalty_name = data.get('penalty_name', '').strip()
    raw_level = data.get('level')
    count = data.get('count', 1)

    if not employee_id or not penalty_name or raw_level is None:
        return jsonify({"error": "Missing required fields."}), 400

    try:
        penalty_level = PenaltyLevel(int(raw_level))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid penalty level selector."}), 400

    try:
        count = int(count)
        if count <= 0: return jsonify({"error": "Count must be > 0."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid type for count."}), 400

    employee = Employee.query.get(employee_id)
    if not employee:
        return jsonify({"error": f"Employee #{employee_id} does not exist."}), 404

    new_penalty = Penalty(
        employee_id=employee_id,
        penalty_name=penalty_name,
        level=penalty_level,
        count=count,
        created_at=get_vietnam_time()
    )

    try:
        db.session.add(new_penalty)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database persistence issue.", "details": str(e)}), 500

    return jsonify({
        "success": True,
        "message": f"Penalty successfully logged for {employee.name}.",
        "penalty": {
            "id": new_penalty.id,
            "employee_id": new_penalty.employee_id,
            "penalty_name": new_penalty.penalty_name,
            "level": new_penalty.level.value,
            "count": new_penalty.count,
            "created_at": new_penalty.created_at.isoformat()
        }
    }), 201
    
@penalties_bp.route('/<int:penalty_id>', methods=['PUT'])
def update_penalty(penalty_id):
    penalty = Penalty.query.get(penalty_id)
    if not penalty:
        return jsonify({"error": f"Penalty record #{penalty_id} does not exist."}), 404

    data = request.get_json() or {}
    penalty_name = data.get('penalty_name', '').strip()
    raw_level = data.get('level')
    count = data.get('count')

    if not penalty_name or raw_level is None or count is None:
        return jsonify({"error": "Missing modified properties."}), 400

    try:
        penalty.level = PenaltyLevel(int(raw_level))
        penalty.count = int(count)
        if penalty.count <= 0: raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid metrics or level enum option matching rules."}), 400

    penalty.penalty_name = penalty_name
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database persistence update error.", "details": str(e)}), 500

    return jsonify({"success": True, "message": "Record successfully updated."}), 200