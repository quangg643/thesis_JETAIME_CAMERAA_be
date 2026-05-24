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
        query = query.filter(Rental.order_status == status_filter.lower())

    if camera_name_filter:
        query = query.filter(Product.name == camera_name_filter)

    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Rental.start_time >= start_dt)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Rental.start_time <= end_dt)
        except ValueError:
            pass

    pagination = query.order_by(Rental.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    results = []

    
    for item in pagination.items:
        delta = item.expected_return_time - item.start_time
        total_seconds = int(delta.total_seconds())

        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

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
            "start_time": item.start_time.isoformat(),
            "expected_return_time": item.expected_return_time.isoformat(),
            "deposit_method": item.deposit_method,
            "customer_name": item.customer.name,
            "phone": item.customer.phone,
            "order_status": item.order_status.value,
            "payment_status": item.payment_status.value,
            "notes": item.note
        })

    return jsonify({
        "data": results,
        "total": pagination.total,
        "pages": pagination.pages
    })

@rental_bp.route('/<int:rental_id>', methods=['GET'])
@jwt_required()
def get_rental_by_id(rental_id):
    item = Rental.query.options(
        db.joinedload(Rental.pic_on),
        db.joinedload(Rental.pic_off_handover),
        db.joinedload(Rental.pic_off_return),
        db.joinedload(Rental.customer)
    ).get_or_404(rental_id)

    delta = item.expected_return_time - item.start_time
    total_seconds = int(delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    duration_display = " ".join(parts) if parts else "0m"

    return jsonify({
        "success": True,
        "data": {
            "id": item.id,
            "date": item.start_time.strftime('%d/%m/%Y'),
            "camera": f"{item.camera.product.name} ({item.camera.identifier})",
            "camera_id": item.camera_id,
            "duration": duration_display,
            "start_time": item.start_time.isoformat(),
            "expected_return_time": item.expected_return_time.isoformat(),
            "deposit_method": item.deposit_method,
            "status": item.order_status.value if hasattr(item.order_status, 'value') else item.status,

            "customer_id": item.customer_id,
            "customer_name": item.customer.name,
            "phone": item.customer.phone,
            "customer_email": item.customer.email or "",
            "customer_address": item.customer.address or "",
            "gender": item.customer.gender.value if item.customer.gender else "MALE",
            "notes": item.note or "",

            "actual_return_date": item.actual_return_date or "",
            "rental_fee": item.rental_fee or "",
            "penalty_fee": item.penalty_fee or "",
            "total_amount": item.total_amount or "",
            "payment_status": item.payment_status or "",

            "pic_on_id": item.pic_on.id if item.pic_on else None,
            "pic_on_name": item.pic_on.name if item.pic_on else "N/A",
            "pic_on_email": item.pic_on.email if item.pic_on else "N/A",
            "pic_on_phone": item.pic_on.phone if item.pic_on else "N/A",

            "pic_off_id": item.pic_off_handover.id if item.pic_off_handover else None,
            "pic_off_name": item.pic_off_handover.name if item.pic_off_handover else "N/A",
            "pic_off_email": item.pic_off_handover.email if item.pic_off_handover else "N/A",
            "pic_off_phone": item.pic_off_handover.phone if item.pic_off_handover else "N/A",

            "pic_off_return_id": item.pic_off_return.id if item.pic_off_return else None,
            "pic_off_return_name": item.pic_off_return.name if item.pic_off_return else "N/A",
            "pic_off_return_email": item.pic_off_return.email if item.pic_off_return else "N/A",
            "pic_off_return_phone": item.pic_off_return.phone if item.pic_off_return else "N/A",
        }
    }), 200

@rental_bp.route('/create', methods=['POST'])
@role_required([UserRole.STAFF_ON])
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
                      'start_time', 'expected_return_time', 'deposit_method']
    
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
            pic_on_id=current_user_id,
            start_time=start_time,
            expected_return_time=expected_return_time,
            rental_fee=rental_fee,
            deposit_method=data['deposit_method'],
            payment_status=PaymentEnum.WAITING.value,
            order_status=RentalStatus.PENDING_PICKUP.value,
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
    
@rental_bp.route('/<int:rental_id>', methods=['PUT'])
@role_required([UserRole.STAFF_ON])
def update_rental(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    
    if rental.order_status != RentalStatus.PENDING_PICKUP:
        return jsonify({
            "error": "Update forbidden", 
            "details": f"Only rentals in 'PENDING_PICKUP' status can be modified. Current status: {rental.order_status.value}"
        }), 400

    data = request.get_json()
    
    try:
        if 'deposit_method' in data:
            rental.deposit_method = data['deposit_method']
        if 'note' in data:
            rental.note = data['note']
            
        # 2. Update Times & Recalculate Fee
        if 'start_time' in data or 'expected_return_time' in data:
            if 'start_time' in data:
                rental.start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            if 'expected_return_time' in data:
                rental.expected_return_time = datetime.fromisoformat(data['expected_return_time'].replace('Z', '+00:00'))
            
            if rental.start_time >= rental.expected_return_time:
                return jsonify({"error": "Return time must be after start time"}), 400
                
            duration = rental.expected_return_time - rental.start_time
            rental.rental_fee = calculate_initial_fee(rental.camera.product, duration)

        db.session.commit()
        return jsonify({"success": True, "message": "Rental updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Update failed", "details": str(e)}), 500

@rental_bp.route('/<int:rental_id>/return', methods=['PUT'])
@role_required([UserRole.STAFF_OFF])
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
    vn_now_naive = vn_now.replace(tzinfo=None)
    rental.actual_return_date = vn_now

    rental.pic_off_return_id = get_jwt_identity()
    
    penalty_fee = 0
    hours_late = 0

    if vn_now_naive < rental.expected_return_time:
        actual_duration = vn_now_naive - rental.start_time
        if actual_duration.total_seconds() < 0:
            actual_duration = rental.expected_return_time - rental.start_time
            
        product = rental.camera.product
        rental.rental_fee = calculate_initial_fee(product, actual_duration)

    if vn_now_naive > rental.expected_return_time:
        overdue_duration = vn_now_naive - rental.expected_return_time
        total_seconds_late = overdue_duration.total_seconds()

        # 1. Apply the 15-minute grace period check (900 seconds)
        if total_seconds_late > 900:
            product = rental.camera.product
            
            # 2. Total hours late (rounded up, as per your original logic)
            total_hours_late = math.ceil(total_seconds_late / 3600)
            
            # 3. Split into days and remaining hours
            days_late = total_hours_late // 24
            remaining_hours_late = total_hours_late % 24
            
            # 4. Calculate penalty using both DB columns
            penalty_fee = (days_late * product.additional_day_price) + \
                          (remaining_hours_late * product.additional_hour_price)
            
            # For your JSON response data tracker
            hours_late = total_hours_late 
        else:
            # Late but within the 15-minute grace window
            hours_late = 0
            penalty_fee = 0

    rental.penalty_fee = penalty_fee
    rental.total_amount = rental.rental_fee + penalty_fee
    rental.camera.status = CameraStatus.AVAILABLE.value
    rental.order_status = RentalStatus.COMPLETED.value
    

    try:
        db.session.commit()
            
        return jsonify({
            "success": True,
            "message": "Return processed successfully",
            "data": {
                "rental_fee": rental.rental_fee,
                "late_hours": hours_late,
                "penalty_fee": penalty_fee,
                "total_amount": rental.total_amount,
                "actual_return_date": vn_now_naive.strftime('%Y-%m-%d %H:%M:%S'),
                "pic_off_name": rental.pic_off_return.name if rental.pic_off_return else "N/A"
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@rental_bp.route('/<int:rental_id>/handover', methods=['PUT'])
@role_required([UserRole.STAFF_OFF])
def handover_camera(rental_id):
    rental = Rental.query.get_or_404(rental_id)
    data = request.get_json()
    
    new_camera_id = data.get('new_camera_id')
    old_camera_id = rental.camera_id
    
    if new_camera_id and int(new_camera_id) != old_camera_id:
        old_camera = Camera.query.get(old_camera_id)
        if old_camera:
            old_camera.status = CameraStatus.AVAILABLE.value
        
        rental.camera_id = new_camera_id
        current_camera = Camera.query.get_or_404(new_camera_id)
    else:
        current_camera = Camera.query.get_or_404(old_camera_id)

    # 2. Update current camera status to RENTED
    current_camera.status = CameraStatus.RENTED.value

    # Date handling logic
    start_time_str = data.get('start_time')
    return_time_str = data.get('expected_return_time')

    new_start = datetime.fromisoformat(start_time_str) if start_time_str else rental.start_time
    new_return = datetime.fromisoformat(return_time_str) if return_time_str else rental.expected_return_time

    if new_return <= new_start:
        return jsonify({"error": "Expected return date must be after the pickup date"}), 400

    # Fee and Status updates
    duration = new_return - new_start
    rental.rental_fee = calculate_initial_fee(current_camera.product, duration)
    
    rental.start_time = new_start
    rental.expected_return_time = new_return
    rental.order_status = RentalStatus.ACTIVE.value
    rental.pic_off_handover_id = get_jwt_identity()

    try:
        db.session.commit()
        return jsonify({"message": "Handover successful"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@rental_bp.route('/<int:rental_id>', methods=['DELETE'])
@role_required([UserRole.STAFF_ON])
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