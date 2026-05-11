import math

from flask import Blueprint, request, jsonify
from datetime import date, datetime

from flask_jwt_extended import get_jwt_identity, jwt_required
from app.decorators import role_required
from app.enums import CameraStatus, PaymentEnum, RentalStatus, UserRole
from app.helpers import calculate_initial_fee, get_vietnam_time
from app.models import  Kpi, Product,  Shift, ShiftAssigned, db, Rental, Camera, Customer

rental_bp = Blueprint('rentals', __name__)

vn_now = get_vietnam_time() 
current_time = vn_now.time()
today_date = vn_now.date()


@rental_bp.route('/', methods=['GET'])
@jwt_required()
def get_rentals():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('search')

    status_filter = request.args.get('status')
    camera_name_filter = request.args.get('camera')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Join Rental -> Camera -> Product and Customer
    query = Rental.query\
        .join(Camera, Rental.camera_id == Camera.id)\
        .join(Product, Camera.product_id == Product.id)\
        .join(Customer, Rental.customer_id == Customer.id)

    if search_query:
        search_all = f"%{search_query}%"
        query = query.filter(
            (Customer.name.ilike(search_all)) | 
            (Product.name.ilike(search_all)) |
            (Camera.identifier.ilike(search_all))
        )

    if status_filter:
        # Assumes status in DB is an Enum; .value might be needed depending on your model
        query = query.filter(Rental.status == status_filter.lower())

    if camera_name_filter:
        # Filter by the Product name specifically
        query = query.filter(Product.name == camera_name_filter)

    # 5. Apply Date Range Filtering
    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Rental.start_time >= start_dt)
        except ValueError:
            pass # Ignore invalid date formats

    if end_date_str:
        try:
            # We add 23:59:59 to include the entire end day
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Rental.start_time <= end_dt)
        except ValueError:
            pass

    pagination = query.order_by(Rental.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    results = []

    
    for item in pagination.items:
        # Business logic: Combine Product Name and Unit Identifier
        delta = item.expected_return_time - item.start_time
        total_seconds = int(delta.total_seconds())

        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        # Build a readable string
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")

        duration_display = " ".join(parts) if parts else "0m"

        gear_display = f"{item.camera.product.name} ({item.camera.identifier})"
        
        results.append({
            "id": item.id,
            "date": item.start_time.strftime('%d/%m/%Y'),
            "camera": gear_display,
            "duration": duration_display,
            "start_time": item.start_time,
            "expected_return_time": item.expected_return_time,
            "fee": item.total_amount,
            "deposit_method": item.deposit_method,
            "customer_name": item.customer.name,
            "phone": item.customer.phone,
            "status": item.status.value,
            "notes": item.note
        })

    return jsonify({
        "data": results,
        "total": pagination.total,
        "pages": pagination.pages
    })

@rental_bp.route('/create', methods=['POST'])
@role_required(UserRole.STAFF_ON)
def create_rental():
    """
    Create a new rental reservation
    ---
    tags:
      - Rentals
    description: >
      Creates a rental record and sets camera status to RESERVED. 
      Automatically increments the employee's KPI (no_customer) if performed during their shift.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - customer_id
            - camera_id
            - start_time
            - expected_return_time
            - deposit_amount
            - deposit_method
          properties:
            customer_id: {type: integer}
            camera_id: {type: integer}
            start_time: {type: string, format: date-time, example: "2026-04-01T10:00:00Z"}
            expected_return_time: {type: string, format: date-time, example: "2026-04-02T10:00:00Z"}
            deposit_amount: {type: integer}
            deposit_method: {type: string, enum: [cash, transfer]}
            note: {type: string}
    responses:
      201:
        description: Rental reserved successfully
      400:
        description: Invalid date range or camera not available
      404:
        description: Customer or Camera not found
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()

    required_fields = ['customer_id', 'camera_id', 
                      'start_time', 'expected_return_time', 'deposit_amount', 'deposit_method']
    
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    try:
        start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
        expected_return_time = datetime.fromisoformat(data['expected_return_time'].replace('Z', '+00:00'))
    except ValueError:
        return jsonify({"error": "Invalid date format. Use ISO format (e.g. 2026-04-01T10:00:00)"}), 400
    
    #validate in FE
    if start_time >= expected_return_time:
        return jsonify({"error": "expected_return_time must be after start_time"}), 400
    #validate in FE
    if start_time < datetime.utcnow():
        return jsonify({"error": "start_time cannot be in the past"}), 400

    if not Customer.query.get(data['customer_id']):
        return jsonify({"error": "Customer not found"}), 404
    
    camera = Camera.query.get_or_404(data['camera_id'])

    product = camera.product
    duration = expected_return_time - start_time
    rental_fee = calculate_initial_fee(product, duration)

    if camera.status != CameraStatus.AVAILABLE:
        return jsonify({"error": "Camera is not available for reservation"}), 400

    try:
        new_rental = Rental(
            customer_id=data['customer_id'],
            camera_id=data['camera_id'],
            employee_id=current_user_id,
            start_time=start_time,
            expected_return_time=expected_return_time,
            rental_fee=rental_fee,
            deposit_amount=data['deposit_amount'],
            deposit_method=data['deposit_method'],
            deposit_status='paid',
            payment_status=PaymentEnum.WAITING.value,
            status="PENDING_PICKUP",
            note=data['note']
        )
        
        camera.status = CameraStatus.RESERVED 
        
        db.session.add(new_rental)

        active_assignment = db.session.query(ShiftAssigned).join(Shift).filter(
            ShiftAssigned.employee_id == current_user_id,
            ShiftAssigned.assigned_date == today_date,
            Shift.start_time <= current_time,
            Shift.end_time >= current_time,
        ).first()

        shift_id = active_assignment.shift_id if active_assignment else None

        if shift_id is not None:            
            kpi_record = Kpi.query.filter(
                Kpi.employee_id == current_user_id,
                Kpi.shift_assigned_id == shift_id,
                db.func.date(Kpi.created_at) == today_date
            ).first()

            if kpi_record:
                kpi_record.no_customer = (kpi_record.no_customer or 0) + 1
            else:
                new_kpi = Kpi(
                    employee_id=current_user_id,
                    shift_assigned_id=shift_id,
                    no_customer=1,
                    created_at=vn_now
                )
                db.session.add(new_kpi)
        else:
            print(f"Rental created by {current_user_id} outside of shift hours. No KPI added.")

        db.session.commit()

        return jsonify({"message": "Rental reserved. Customer must visit shop for pickup."}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500

@rental_bp.route('/<int:rental_id>/return', methods=['PUT'])
@role_required(UserRole.STAFF_OFF)
def return_camera(rental_id):
    """
    Process camera return and calculate final fees
    ---
    tags:
      - Rentals
    description: Calculates penalty fees based on hourly rates if returned late. Sets camera status back to AVAILABLE.
    parameters:
      - name: rental_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Return processed with fee breakdown
        schema:
          properties:
            initial_fee: {type: integer}
            penalty_fee: {type: integer}
            late_hours: {type: integer}
            total_final_amount: {type: integer}
      400:
        description: Camera already returned
    """
    rental = Rental.query.get_or_404(rental_id)
    if rental.actual_return_date:
        return jsonify({"error": "Already returned"}), 400

    vn_now = get_vietnam_time()
    rental.actual_return_date = vn_now
    
    penalty_fee = 0
    if vn_now > rental.expected_return_time:

        overdue_duration = vn_now - rental.expected_return_time
        total_seconds_late = overdue_duration.total_seconds()

        hours_late = math.ceil(total_seconds_late / 3600)
        
        product = rental.camera.product
        penalty_fee = hours_late * product.additional_hour_price

    try:
        rental.camera.status = CameraStatus.AVAILABLE.value
        db.session.commit()
            
        return jsonify({
            "message": "Return processed",
            "initial_fee": rental.rental_fee,
            "late_hours": hours_late if penalty_fee > 0 else 0,
            "penalty_fee": penalty_fee,
            "total_final_amount": rental.rental_fee + penalty_fee
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@rental_bp.route('/<int:rental_id>/handover', methods=['POST'])
@role_required(UserRole.STAFF_OFF)
def handover_camera(rental_id):
    """
    Process physical camera handover to customer
    ---
    tags:
      - Rentals
    parameters:
      - name: rental_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - action
          properties:
            action: 
              type: string
              enum: [approve, fix]
              description: "'approve' starts the rental. 'fix' moves camera to maintenance and requires a replacement."
            replacement_camera_id: 
              type: integer
              description: Required only if action is 'fix'
    responses:
      200:
        description: Handover processed successfully
      400:
        description: Missing replacement camera ID
    """
    rental = Rental.query.get_or_404(rental_id)
    data = request.get_json()
    
    action = data.get('action') 
    camera = rental.camera

    try:
        if action == 'approve':
            camera.status = CameraStatus.RENTED
            rental.status = RentalStatus.ACTIVE
            msg = "Camera handed over successfully."

        elif action == 'fix':
            camera.status = CameraStatus.MAINTENANCE
            
            new_camera_id = data.get('replacement_camera_id')
            if not new_camera_id:
                return jsonify({"error": "Replacement camera ID required if original is rejected"}), 400
            
            new_camera = Camera.query.get_or_404(new_camera_id)
            if new_camera.status != CameraStatus.AVAILABLE:
                return jsonify({"error": "Replacement camera is not available"}), 400
            
            rental.camera_id = new_camera.id
            new_camera.status = CameraStatus.RENTED
            rental.status = RentalStatus.ACTIVE
            msg = "Original camera moved to maintenance. Replacement issued."
        
        db.session.commit()
        return jsonify({"message": msg}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@rental_bp.route('/<int:rental_id>', methods=['DELETE'])
@role_required(UserRole.STAFF_ON)
def delete_rental(rental_id):
    """
    Cancel a pending rental
    ---
    tags:
      - Rentals
    description: >
      Only rentals in 'PENDING_PICKUP' status can be deleted. 
      Deleting a rental will decrement the associated employee's KPI and release the camera.
    parameters:
      - name: rental_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Rental deleted and KPI adjusted
      400:
        description: Cannot delete (e.g. rental is already active)
    """
    try:
        rental = Rental.query.get_or_404(rental_id)

        if rental.status != "PENDING_PICKUP":
            return jsonify({
                "error": "Cannot delete rental", 
                "details": f"Only rentals with status 'PENDING_PICKUP' can be deleted. Current status: {rental.status}"
            }), 400

        rental_created_at = rental.created_at
        rental_time = rental_created_at.time()
        rental_date = rental_created_at.date()

        past_assignment = db.session.query(ShiftAssigned).join(Shift).filter(
            ShiftAssigned.employee_id == rental.employee_id,
            Shift.start_time <= rental_time,
            Shift.end_time >= rental_time,
            db.func.date(ShiftAssigned.assigned_date) == rental_date
        ).first()

        shift_id = past_assignment.shift_id if past_assignment else None

        kpi_record = Kpi.query.filter(
            Kpi.employee_id == rental.employee_id,
            Kpi.shift_assigned_id == shift_id,
            db.func.date(Kpi.created_at) == rental_date
        ).first()

        if kpi_record and kpi_record.no_customer > 0:
            kpi_record.no_customer -= 1

        camera = Camera.query.get(rental.camera_id)
        if camera:
            camera.status = CameraStatus.AVAILABLE

        db.session.delete(rental)
        db.session.commit()

        return jsonify({"message": f"Rental #{rental_id} (Pending) deleted and KPI adjusted"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete rental", "details": str(e)}), 500