from flask import Blueprint, request, jsonify
from datetime import datetime

from flask_jwt_extended import jwt_required
from app.decorators import role_required
from app.enums import PaymentEnum, UserRole
from app.models import Rental, db, Customer

customers_bp = Blueprint('customers', __name__)

@customers_bp .route('/', methods=['GET'])
@jwt_required()
def get_all_customers():
    """
    Get a list of customers with search and pagination
    ---
    tags:
      - Customers
    security:
      - cookieAuth: []
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
        default: 20
    responses:
      200:
        description: A paginated list of customers
        schema:
          properties:
            customers:
              type: array
              items:
                properties:
                  id: {type: integer}
                  name: {type: string}
                  email: {type: string}
                  phone: {type: string}
                  address: {type: string}
                  created_at: {type: string, format: date-time}
            total: {type: integer}
            pages: {type: integer}
            current_page: {type: integer}
            per_page: {type: integer}
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    search = request.args.get('search', None, type=str)

    query = Customer.query

    if search:
        query = query.filter(
            (Customer.name.ilike(f'%{search}%')) |
            (Customer.email.ilike(f'%{search}%')) |
            (Customer.phone.ilike(f'%{search}%'))
        )

    pagination = query.order_by(Customer.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    customers = [{
        'id': c.id,
        'name': c.name,
        'email': c.email,
        'phone': c.phone,
        'address': c.address,
        'created_at': c.created_at.isoformat() if c.created_at else None
    } for c in pagination.items]

    return jsonify({
        'customers': customers,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page
    }), 200


@customers_bp .route('/<int:id>', methods=['GET'])
@jwt_required()
def get_customer(id):
    """
    Get detailed information for a specific customer
    ---
    tags:
      - Customers
    security:
      - cookieAuth: []
    parameters:
      - name: id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Customer details returned
      404:
        description: Customer not found
    """
    customer = Customer.query.get_or_404(id)
    
    return jsonify({
        'id': customer.id,
        'name': customer.name,
        'email': customer.email,
        'phone': customer.phone,
        'address': customer.address,
        'created_at': customer.created_at.isoformat() if customer.created_at else None
    }), 200


@customers_bp.route('/', methods=['POST'])
@jwt_required()
def create_customer():
    """
    Register a new customer
    ---
    tags:
      - Customers
    security:
      - cookieAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - phone
          properties:
            name: {type: string, example: "Jane Doe"}
            phone: {type: string, example: "0987654321"}
            email: {type: string, example: "jane@example.com"}
            address: {type: string, example: "123 Main St, Hanoi"}
    responses:
      201:
        description: Customer created successfully
      400:
        description: Name and phone are required
      409:
        description: Customer with this name or email already exists
    """
    data = request.get_json()

    if not data or not data.get('name') or not data.get('phone'):
        return jsonify({'error': 'Name and phone are required'}), 400

    if Customer.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Customer with this name already exists'}), 409

    if data.get('email') and Customer.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Customer with this email already exists'}), 409

    new_customer = Customer(
        name=data['name'],
        email=data.get('email'),
        phone=data['phone'],
        address=data.get('address')
    )

    db.session.add(new_customer)
    db.session.commit()

    return jsonify({
        'message': 'Customer created successfully',
        'customer': {
            'id': new_customer.id,
            'name': new_customer.name,
            'email': new_customer.email,
            'phone': new_customer.phone,
            'address': new_customer.address,
            'created_at': new_customer.created_at.isoformat()
        }
    }), 201


@customers_bp.route('/<int:id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_customer(id):
    """
    Update customer information
    ---
    tags:
      - Customers
    security:
      - cookieAuth: []
    parameters:
      - name: id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            name: {type: string}
            phone: {type: string}
            email: {type: string}
            address: {type: string}
    responses:
      200:
        description: Customer updated successfully
      400:
        description: No data provided
      409:
        description: Conflicts with existing customer name or email
      404:
        description: Customer not found
    """
    customer = Customer.query.get_or_404(id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'name' in data:
        existing = Customer.query.filter_by(name=data['name']).first()
        if existing and existing.id != id:
            return jsonify({'error': 'Customer with this name already exists'}), 409
        customer.name = data['name']

    if 'email' in data:
        if data['email']:
            existing = Customer.query.filter_by(email=data['email']).first()
            if existing and existing.id != id:
                return jsonify({'error': 'Customer with this email already exists'}), 409
        customer.email = data.get('email')

    if 'phone' in data:
        customer.phone = data['phone']

    if 'address' in data:
        customer.address = data.get('address')

    db.session.commit()

    return jsonify({
        'message': 'Customer updated successfully',
        'customer': {
            'id': customer.id,
            'name': customer.name,
            'email': customer.email,
            'phone': customer.phone,
            'address': customer.address,
            'created_at': customer.created_at.isoformat() if customer.created_at else None
        }
    }), 200

@customers_bp.route('/<int:id>', methods=['DELETE'])
@role_required(UserRole.MANAGER)
def delete_customer(id):
    """
    Delete a customer (Manager only)
    ---
    tags:
      - Customers
    security:
      - cookieAuth: []
    description: Deletion is only allowed if the customer has no active rentals and no unpaid fees.
    parameters:
      - name: id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Customer deleted successfully
      400:
        description: Cannot delete due to active rentals or unpaid fees
      401:
        description: Unauthorized / Insufficient permissions
      404:
        description: Customer not found
    """
    customer = Customer.query.get_or_404(id)

    unpaid_rentals = Rental.query.filter(
        Rental.customer_id == id,
        Rental.payment_status != PaymentEnum.PAID
    ).first()

    if unpaid_rentals:
        return jsonify({
            "success": False,
            "error": "Cannot delete customer: This customer has unpaid rental fees."
        }), 400

    
    active_rentals = Rental.query.filter(
        Rental.customer_id == id,
        Rental.actual_return_date == None
    ).first()

    if active_rentals:
        return jsonify({
            "success": False,
            "error": "Cannot delete customer: This customer currently has an active camera rental."
        }), 400

    try:
        db.session.delete(customer)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Customer '{customer.name}' (ID: {id}) deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": "Database error during deletion",
            "details": str(e)
        }), 500
