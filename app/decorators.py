from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, jwt_required

def role_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_role = claims.get('role')

            if user_role not in [r.value for r in allowed_roles]:
                return jsonify({
                    'success': False,
                    'message': 'Access forbidden'
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator