from datetime import datetime, timedelta

from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import get_current_user, jwt_required
from sqlalchemy import or_
from app import db
from app.decorators import role_required
from app.enums import AccountStatus
from app.helpers import get_vietnam_time
from app.models import Employee, UserRole

employees_bp = Blueprint('employees', __name__)

@employees_bp.route('/offboard/<int:id>', methods=['POST'])
@role_required([UserRole.ADMIN, UserRole.MANAGER])
def offboard(id):
    """
    Offboard an employee
    ---
    tags:
      - Employees
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: ID of the employee to offboard
    responses:
      200:
        description: Employee status updated to OFFBOARDED
      400:
        description: Invalid request (self-offboarding or already offboarded)
      500:
        description: Database error
    """
    vn_now = get_vietnam_time() 
    
    employee = Employee.query.get_or_404(id)

    current_user_id = get_current_user()
    if employee.id == int(current_user_id):
        return jsonify({"error": "You cannot offboard yourself"}), 400
    
    if employee.status == AccountStatus.OFFBOARDED:
        return jsonify({"error": "Employee is already offboarded"}), 400

    try:
        employee.status = AccountStatus.OFFBOARDED
        employee.offboard_date = vn_now

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Employee {employee.name} (ID: {employee.id}) status updated to OFFBOARDED.",
            "offboard_date": employee.offboard_date.isoformat(),
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Offboard error for employee {id}: {str(e)}")
        return jsonify({"error": "Failed to update employee status", "details": str(e)}), 500

@employees_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_employees():
    """
    Get all active employees
    ---
    tags:
      - Employees
    parameters:
      - name: search
        in: query
        type: string
        description: Search by name, email, or phone
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 5
    responses:
      200:
        description: A paginated list of employees
        schema:
          properties:
            success:
              type: boolean
            employees:
              type: array
              items:
                properties:
                  id: {type: integer}
                  name: {type: string}
                  role: {type: string}
                  salary: {type: number}
    """
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 5, type=int), 100)

    query = Employee.query.filter_by(status='ACTIVE').order_by(Employee.name.asc())

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Employee.name.ilike(search_term),
                Employee.email.ilike(search_term),
                Employee.phone.ilike(search_term)
            )
        )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    employees = pagination.items

    employees_list = []
    for emp in employees:
        if emp.role in [UserRole.STAFF_ON, UserRole.STAFF_OFF]:
            salary_to_show = emp.hour_salary
        else:
            salary_to_show = emp.base_salary

        employees_list.append({
            'id': emp.id,
            'name': emp.name,
            'email': emp.email,
            'phone': emp.phone,
            'role': emp.role.value,
            'gender':emp.gender.value,
            'salary': salary_to_show,
            'created_at': emp.created_at.strftime('%Y-%m-%d %H:%M') if emp.created_at else None
        })

    return jsonify({
        'success': True,
        'count': len(employees_list),
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'per_page': pagination.per_page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
        'employees': employees_list
    }), 200

@employees_bp.route('/<int:employee_id>/update', methods=['PATCH'])
@role_required([UserRole.ADMIN, UserRole.MANAGER])
def update_employee(employee_id):
    """
    Update employee role or salary
    ---
    tags:
      - Employees
    security:
      - cookieAuth: []
    parameters:
      - name: employee_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            role: {type: string, example: "MANAGER"}
            base_salary: {type: number, example: 8000000}
            hour_salary: {type: number, example: 25000}
    responses:
      200:
        description: Employee updated successfully
        schema:
          properties:
            message: {type: string}
            employee_id: {type: integer}
            updated: {type: object}
      400:
        description: Invalid role or salary mismatch (e.g. base_salary for staff)
      404:
        description: Employee not found
    """
    employee = Employee.query.get_or_404(employee_id)
    data = request.get_json()

    role_param = data.get('role')
    base_salary_param = data.get('base_salary')
    hour_salary_param = data.get('hour_salary')

    updated_fields = {}

    if role_param:
        try:
            new_role = UserRole[role_param.upper()]
            if new_role != employee.role:
                # If moving AWAY from Staff roles, reset hourly pay
                staff_roles = [UserRole.STAFF_ON, UserRole.STAFF_OFF]
                if employee.role in staff_roles and new_role not in staff_roles:
                    employee.hour_salary = 0.0
                    updated_fields['hour_salary'] = 0.0
                
                employee.role = new_role
                updated_fields['role'] = new_role.value
        except KeyError:
            return jsonify({"error": f"Invalid role. Valid options: {[r.name for r in UserRole]}"}), 400

    current_role = employee.role
    is_staff = current_role in [UserRole.STAFF_ON, UserRole.STAFF_OFF]

    if base_salary_param is not None:
        if is_staff:
            return jsonify({"error": "STAFF_ON/OFF cannot have a base_salary. Update hour_salary instead."}), 400
        try:
            val = float(base_salary_param)
            if val < 0: raise ValueError
            employee.base_salary = val
            updated_fields['base_salary'] = val
        except ValueError:
            return jsonify({"error": "Base salary must be a non-negative number"}), 400

    if hour_salary_param is not None:
        if not is_staff:
            return jsonify({"error": "Only STAFF_ON/OFF can have an hour_salary."}), 400
        try:
            val = float(hour_salary_param)
            if val < 0: raise ValueError
            employee.hour_salary = val
            updated_fields['hour_salary'] = val
        except ValueError:
            return jsonify({"error": "Hour salary must be a non-negative number"}), 400

    if not updated_fields:
        return jsonify({"message": "No changes detected or provided"}), 200

    try:
        db.session.commit()
        return jsonify({
            "message": "Employee updated successfully",
            "employee_id": employee.id,
            "updated": updated_fields
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500