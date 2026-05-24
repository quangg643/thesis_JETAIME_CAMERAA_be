from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, jwt_required

def role_required(allowed_roles):
    """
    Accepts a list of roles, e.g., @role_required([UserRole.ADMIN, UserRole.MANAGER])
    Also gracefully handles empty lists for general authentication check.
    """
    def decorator(fn):
        @jwt_required()
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not allowed_roles:
                return fn(*args, **kwargs)

            claims = get_jwt()
            user_role = claims.get('role')

            allowed_values = [r.value if hasattr(r, 'value') else r for r in allowed_roles]

            if user_role not in allowed_values:
                return jsonify({
                    'success': False,
                    'message': 'Access forbidden'
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator