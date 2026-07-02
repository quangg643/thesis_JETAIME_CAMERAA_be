from flask import Blueprint, request, jsonify
from datetime import datetime, time, timedelta
from sqlalchemy import extract, func, or_
from app import db
from app.decorators import role_required
from app.models import Employee, Kpi, Payroll, Penalty, Rental, Shift, ShiftAssigned
from app.enums import AccountStatus, UserRole
from app.helpers import get_vietnam_time

salaries_bp = Blueprint('salaries', __name__)

@salaries_bp.route('/state', methods=['GET'])
@role_required([UserRole.ADMIN, UserRole.MANAGER])
def get_all_salaries_state():
    """
    Fetch a real-time calculated overview of employee payroll states, including base pay, KPI bonuses, and penalty deductions
    ---
    tags:
      - Salaries & Payroll
    security:
      - cookieAuth: []
    parameters:
      - name: period
        in: query
        type: string
        placeholder: "YYYY-MM"
        description: Target period to analyze. Defaults dynamically to the current Vietnam Year-Month calendar string.
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 10
      - name: search
        in: query
        type: string
        description: Filters output tracking employee names
    responses:
      200:
        description: Array list of live computed wages
        schema:
          type: object
          properties:
            payrolls:
              type: array
              items:
                type: object
                properties:
                  employee_id: {type: integer}
                  employee_name: {type: string}
                  employee_role: {type: string}
                  period: {type: string, example: "2026-03"}
                  total_hours: {type: number, example: 160.5}
                  base_pay: {type: integer, example: 8000000}
                  kpi_bonus: {type: integer, example: 450000}
                  penalty_deduction: {type: integer, example: 100000}
                  final_salary: {type: integer, example: 8350000}
                  status: {type: string, example: "LIVE_MONITORING"}
            total_records: {type: integer}
            current_page: {type: integer}
            total_pages: {type: integer}
      400:
        description: Invalid date period time window string schema matching rules
        schema:
          type: object
          properties:
            error: {type: string, example: "Invalid period format. Use YYYY-MM"}
      500:
        description: Internal database mapping error during commit
    """
    # 1. Period & Pagination parameters
    current_time = get_vietnam_time()
    current_period = current_time.strftime('%Y-%m')
    
    period = request.args.get('period', current_period)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('search', '', type=str).strip()

    try:
        year, month = map(int, period.split('-'))
    except ValueError:
        return jsonify({"error": "Invalid period format. Use YYYY-MM"}), 400

    start_of_month = datetime(year, month, 1)
    if month == 12:
        end_of_month = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_of_month = datetime(year, month + 1, 1) - timedelta(seconds=1)

    # 2. Base Query: Handle inclusion rules (Active or recently offboarded)
    employee_query = Employee.query.filter(
        or_(
            Employee.status == AccountStatus.ACTIVE,
            Employee.offboard_date >= start_of_month
        )
    )

    # Apply backend search filter if requested
    if search_query:
        employee_query = employee_query.filter(Employee.name.ilike(f"%{search_query}%"))

    employee_query = employee_query.order_by(Employee.id.desc())
    
    # Execute backend pagination
    pagination_obj = employee_query.paginate(page=page, per_page=per_page, error_out=False)
    employees = pagination_obj.items

    results = []

    for employee in employees:
        existing_payroll = Payroll.query.filter_by(
            employee_id=employee.id,
            period=period
        ).first()

        # Past Month Isolation check
        if existing_payroll and period < current_period:
            results.append({
                "employee_id": employee.id,
                "employee_name": employee.name,
                "employee_role":employee.role,
                "period": period,
                "base_pay": existing_payroll.init_salary,
                "kpi_bonus": existing_payroll.bonus,
                "penalty_deduction": existing_payroll.penalty,
                "final_salary": existing_payroll.total_pay,
                "status": "ISOLATED_HISTORICAL_DATA"
            })
            continue

        # Continuous Live calculations
        upper_bound_date = end_of_month.date()
        if employee.offboard_date and employee.offboard_date < end_of_month:
            upper_bound_date = employee.offboard_date.date()

        assignments = ShiftAssigned.query.filter(
            ShiftAssigned.employee_id == employee.id,
            ShiftAssigned.assigned_date >= start_of_month.date(),
            ShiftAssigned.assigned_date <= upper_bound_date
        ).all()

        total_hours = sum(asn.shift.hours for asn in assignments)
        total_kpi_bonus = 0
        
        for asn in assignments:
            shift = asn.shift
            if shift.start_time < time(22, 0):
                kpi_record = Kpi.query.filter_by(shift_assigned_id=asn.id).first()
                if kpi_record and kpi_record.no_customer >= 10:
                    shift_start = datetime.combine(asn.assigned_date, shift.start_time)
                    shift_end = datetime.combine(asn.assigned_date, shift.end_time)
                    
                    # Target pic_on_id as primary creator context
                    revenue = db.session.query(db.func.sum(Rental.total_amount)).filter(
                        Rental.pic_on_id == employee.id,
                        Rental.created_at >= shift_start,
                        Rental.created_at <= shift_end
                    ).scalar() or 0
                    total_kpi_bonus += (revenue * 0.01)

        base_pay_total = total_hours * employee.hour_salary

        penalties = Penalty.query.filter(
            Penalty.employee_id == employee.id,
            extract('year', Penalty.created_at) == year,
            extract('month', Penalty.created_at) == month,
            Penalty.created_at <= datetime.combine(upper_bound_date, time.max)
        ).all()
        
        total_penalty = sum(p.level * 50000 * p.count for p in penalties)
        total_pay = max(0, base_pay_total + total_kpi_bonus - total_penalty)

        # Upsert Live Snapshot Record
        if not existing_payroll:
            existing_payroll = Payroll(
                employee_id=employee.id,
                period=period,
                init_salary=base_pay_total,
                bonus=int(total_kpi_bonus),
                penalty=total_penalty,
                total_pay=total_pay,
                checking_date=current_time.date()
            )
            db.session.add(existing_payroll)
        else:
            existing_payroll.init_salary = base_pay_total
            existing_payroll.bonus = int(total_kpi_bonus)
            existing_payroll.penalty = total_penalty
            existing_payroll.total_pay = total_pay
            existing_payroll.checking_date = current_time.date()

        results.append({
            "employee_id": employee.id,
            "employee_name": employee.name,
            "employee_role":employee.role,
            "period": period,
            "total_hours": total_hours,
            "base_pay": base_pay_total,
            "kpi_bonus": total_kpi_bonus,
            "penalty_deduction": total_penalty,
            "final_salary": total_pay,
            "status": "LIVE_MONITORING"
        })

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500

    # Return paginated structure payload wrapper
    return jsonify({
        "payrolls": results,
        "total_records": pagination_obj.total,
        "current_page": pagination_obj.page,
        "total_pages": pagination_obj.pages,
        "per_page": pagination_obj.per_page
    }), 200