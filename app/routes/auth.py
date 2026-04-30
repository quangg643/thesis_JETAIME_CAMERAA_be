from flask import Blueprint, request, jsonify
from app import db
from app.enums import AccountStatus, UserRole
from app.models import Employee, TokenBlocklist
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token, get_current_user, get_jwt, get_jwt_identity, jwt_required, set_access_cookies, set_refresh_cookies, unset_jwt_cookies

auth_bp = Blueprint('auth',__name__)

@auth_bp.route('/signup', methods=['POST'])
def register():
    """
    Register a new employee
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name: {type: string, example: "John Doe"}
            email: {type: string, example: "john@example.com"}
            phone: {type: string, example: "0123456789"}
            gender: {type: string, example: "Male"}
            password: {type: string, example: "06042003"}
            role: {type: string, example: "staff_on", description: "Manager, staff_on, or staff_off"}
    responses:
      200:
        description: User created successfully
      400:
        description: User already exists or invalid role
      500:
        description: Database error
    """
    data = request.get_json()

    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    gender = data.get('gender')
    password = data.get('password')
    role = data.get('role')

    existing_user = Employee.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'message': 'User already exists. Please login.'}), 400

    hashed_password = generate_password_hash(password)
    new_user = Employee(name=name, email=email, password=hashed_password, role=role, phone = phone, gender=gender)

    try:
        if role in (UserRole.STAFF_ON.value, UserRole.STAFF_OFF.value):
            new_user.hour_salary = 20000
            new_user.base_salary = None

        elif role == UserRole.MANAGER.value:
            new_user.base_salary = 7500000
            new_user.hour_salary = None

        else:
            return jsonify({'message': 'Invalid role'}), 400

    except Exception as e:
        return jsonify({'message': 'Error setting salary', 'error': str(e)}), 500
    
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
    'success': True,
    'message': 'Add user successful',
    'user': {
        'name': new_user.name,
        'email': new_user.email,
        'role': new_user.role.value,
        'base_salary': int(new_user.base_salary) if new_user.base_salary else None,
        'hour_salary': int(new_user.hour_salary) if new_user.hour_salary else None
    }
    }), 200

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Employee Login
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            email: {type: string, example: "john@example.com"}
            password: {type: string, example: "06042003"}
    responses:
      200:
        description: Login successful. JWT cookies are set in headers.
      401:
        description: Invalid credentials or account offboarded
    """

    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    # remember = data.get('remember', False)
    
    #validate in FE
    if not email or not password:
        return jsonify({
            'success': False,
            'message': 'Email and password are required'
        }), 400

    user = Employee.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({
            'success': False,
            'message': 'Invalid email or password'
        }), 401
    
    if user.status != AccountStatus.ACTIVE:
        return jsonify({
            'success': False,
            'message': 'The account is offboarded, cannot be accessed'
        }), 401
    
    payload = {
        'id': user.id,
        'role': user.role.value,
        'name': user.name,
        'email': user.email,
    }

    # if remember:
    #     expires = timedelta(days=30)
    # else:
    #     expires = timedelta(hours=1)

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims=payload
    )

    refresh_token = create_refresh_token(
        identity=str(user.id),
        additional_claims=payload,
        # expires_delta=expires
    )

    resp = jsonify({
            'message': 'Login successful',
        })
    
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)

    return resp, 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh Access Token
    ---
    tags:
      - Authentication
    security:
      - cookieAuth: []
    responses:
      200:
        description: Token refreshed
      401:
        description: Refresh token missing or invalid
    """
    current_user_id = get_jwt_identity()

    user = Employee.query.get(current_user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 401

    payload = {
        'id': user.id,
        'role': user.role.value,
        'name': user.name,
        'email': user.email,
    }

    new_access_token = create_access_token(identity=str(current_user_id), additional_claims=payload)

    resp = jsonify({"msg": "Token refreshed"})
    set_access_cookies(resp, new_access_token)

    return jsonify({
        'success': True,
        'access_token': new_access_token
    }), 200

@auth_bp.route('/logout', methods=['DELETE'])
@jwt_required()
def logout():
    """
    Revoke Access Token
    ---
    tags:
      - Authentication
    security:
      - cookieAuth: []
    responses:
      200:
        description: Access token revoked
    """
    try:
        jti = get_jwt()["jti"]
        db.session.add(TokenBlocklist(jti=jti))
        db.session.commit()

        resp = jsonify({"msg": "Access token revoked successfully"})
        unset_jwt_cookies(resp)
        return resp, 200

    except Exception:
        return jsonify({"message": "Something went wrong"}), 500

@auth_bp.route('/logout-refresh', methods=['DELETE'])
@jwt_required(refresh=True)
def logout_refresh():
    """
    Revoke Refresh Token
    ---
    tags:
      - Authentication
    security:
      - cookieAuth: []
    responses:
      200:
        description: Refresh token revoked
    """ 
    try:
        jti = get_jwt()["jti"]
        db.session.add(TokenBlocklist(jti=jti))
        db.session.commit()

        resp = jsonify({"msg": "Refresh token revoked successfully"})
        unset_jwt_cookies(resp)
        return resp, 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Something went wrong"}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user_info():
    """
    Get current logged-in user info
    ---
    tags:
      - Authentication
    security:
      - cookieAuth: []
    responses:
      200:
        description: Returns user object
        schema:
          type: object
          properties:
            success: {type: boolean}
            user:
              type: object
              properties:
                id: {type: integer}
                name: {type: string}
                email: {type: string}
                role: {type: string}
      404:
        description: User not found
    """
    user = get_current_user()
    if not user:
        return jsonify({
            'success': False,
            'message': 'User not found'
        }), 404

    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role.value if hasattr(user.role, 'value') else user.role
        }
    }), 200