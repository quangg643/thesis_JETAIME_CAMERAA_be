from flask import Blueprint, request, jsonify
from app import db
from app.models import Employee, Penalty
from app.enums import PenaltyLevel
from app.helpers import get_vietnam_time

penalties_bp = Blueprint('penalties', __name__)

@penalties_bp.route('/', methods=['GET'])
def get_all_penalties():
    """
    Get a paginated list of staff disciplinary penalties with search filters
    ---
    tags:
      - Penalties
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: Page number (defensive fallback to 1 if < 1)
      - name: per_page
        in: query
        type: integer
        default: 10
        description: Items per page (defensive fallback to 10 if < 1)
      - name: search
        in: query
        type: string
        description: Server-side search filter targeting Employee Name, Penalty Name, or Employee ID
    responses:
      200:
        description: Paginated dictionary list of matches
        schema:
          type: object
          properties:
            penalties:
              type: array
              items:
                type: object
                properties:
                  id: {type: integer}
                  employee_id: {type: integer}
                  employee_name: {type: string}
                  penalty_name: {type: string}
                  level: {type: integer, description: "Enum level value matching rules"}
                  count: {type: integer}
                  created_at: {type: string, format: date}
            total: {type: integer}
            pages: {type: integer}
            current_page: {type: integer}
      500:
        description: Server-side database mapping failure
    """
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
    """
    Delete a penalty record by its ID
    ---
    tags:
      - Penalties
    parameters:
      - name: penalty_id
        in: path
        type: integer
        required: true
        description: The unique identifier of the penalty record to delete
    responses:
      200:
        description: Penalty record successfully deleted
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "Penalty record #5 successfully deleted."}
      404:
        description: Penalty record not found
        schema:
          type: object
          properties:
            error: {type: string, example: "Penalty record #5 does not exist."}
      500:
        description: Database rollback error while deleting the record
        schema:
          type: object
          properties:
            error: {type: string, example: "Database error while deleting record."}
            details: {type: string}
    """
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
    """
    Log a new penalty for an employee
    ---
    tags:
      - Penalties
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - employee_id
            - penalty_name
            - level
          properties:
            employee_id: {type: integer, example: 2}
            penalty_name: {type: string, example: "Late Attendance"}
            level: {type: integer, example: 1, description: "Raw integer corresponding to PenaltyLevel enum"}
            count: {type: integer, default: 1, example: 1}
    responses:
      201:
        description: Penalty successfully logged
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "Penalty successfully logged for John Doe."}
            penalty:
              type: object
              properties:
                id: {type: integer}
                employee_id: {type: integer}
                penalty_name: {type: string}
                level: {type: integer}
                count: {type: integer}
                created_at: {type: string, format: date-time}
      400:
        description: Missing required fields, invalid level format, or count <= 0
        schema:
          type: object
          properties:
            error: {type: string, example: "Missing required fields."}
      404:
        description: Target Employee row record not found
        schema:
          type: object
          properties:
            error: {type: string, example: "Employee #2 does not exist."}
      500:
        description: Database persistence transaction failed
        schema:
          type: object
          properties:
            error: {type: string, example: "Database persistence issue."}
            details: {type: string}
    """
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
    """
    Modify an existing penalty record's metrics and metadata
    ---
    tags:
      - Penalties
    parameters:
      - name: penalty_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - penalty_name
            - level
            - count
          properties:
            penalty_name: {type: string, example: "Late Attendance"}
            level: {type: integer, example: 1, description: "PenaltyLevel enum matching rules"}
            count: {type: integer, example: 2, description: "Must be a positive integer (> 0)"}
    responses:
      200:
        description: Penalty record updated successfully
        schema:
          type: object
          properties:
            message: {type: string, example: "Penalty record updated successfully"}
            penalty:
              type: object
              properties:
                id: {type: integer}
                penalty_name: {type: string}
                level: {type: integer}
                count: {type: integer}
      400:
        description: Missing modified properties or invalid metrics/enum types
        schema:
          type: object
          properties:
            error: {type: string, example: "Missing modified properties."}
      404:
        description: Penalty record not found
        schema:
          type: object
          properties:
            error: {type: string, example: "Penalty record #5 does not exist."}
    """
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