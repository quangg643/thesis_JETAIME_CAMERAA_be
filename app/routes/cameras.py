from flask import Blueprint, jsonify, request
import re

from flask_jwt_extended import jwt_required
from sqlalchemy.orm import joinedload

from app.decorators import role_required
from app.enums import CameraStatus, UserRole
from app.models import Camera, Product
from app import db

cameras_bp = Blueprint('cameras', __name__)

@cameras_bp.route('/', methods=['POST'])
@role_required([UserRole.STAFF_OFF])
def add_single_camera():
    """
    Add a new camera instance
    ---
    tags:
      - Cameras
    security:
      - cookieAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - product_id
            - identifier
          properties:
            product_id: {type: integer, example: 1}
            identifier: {type: string, example: "CAM-001", description: "Min 3, Max 50 chars. Alphanumeric, - and _ only."}
    responses:
      201:
        description: Camera created successfully
      400:
        description: Validation error (missing fields, too short/long, invalid characters)
      409:
        description: Identifier already exists
    """

    data = request.get_json()
    product_id = data.get('product_id')
    identifier = data.get('identifier')

    #PAY_ATTENTION: consider validate field in FE
    if not identifier:
        return jsonify({
            "success": False,
            "error": "Missing required parameter: identifier"
        }), 400

    identifier = identifier.strip()

    if len(identifier) < 3:
        return jsonify({
            "success": False,
            "error": "Identifier must be at least 3 characters long"
        }), 400

    if len(identifier) > 50:
        return jsonify({
            "success": False,
            "error": "Identifier is too long (maximum 50 characters)"
        }), 400


    if not re.match(r'^[a-zA-Z0-9\-_]+$', identifier):
        return jsonify({
            "success": False,
            "error": "Identifier can only contain letters, numbers, hyphens (-) and underscores (_)"
        }), 400

    if not product_id:
        return jsonify({
            "success": False,
            "error": "Missing required parameter: product_id"
        }), 400


    try:
        product = Product.query.get_or_404(int(product_id))

        existing_camera = Camera.query.filter_by(identifier=identifier).first()
        if existing_camera:
            return jsonify({
                "success": False,
                "error": f"Camera with identifier '{identifier}' already exists"
            }), 409

        camera = Camera(
            identifier=identifier,
            product_id=product_id,
        )

        db.session.add(camera)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Camera added successfully",
            "camera": {
                "id": camera.id,
                "identifier": camera.identifier,
                "product_id": camera.product_id,
                "product_name": product.name
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Failed to add camera: {str(e)}"
        }), 500

@cameras_bp.route('/<int:camera_id>', methods=['PUT'])
@jwt_required()
def update_camera(camera_id):
    """
    Update camera identifier or status
    ---
    tags:
      - Cameras
    security:
      - cookieAuth: []
    parameters:
      - name: camera_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            identifier: {type: string, example: "CAM-001-NEW"}
            status: {type: string, example: "AVAILABLE", description: "Valid options depend on CameraStatus Enum (except RENTED)"}
    responses:
      200:
        description: Camera updated successfully
      400:
        description: Invalid status, identifier, or manual RENTED status attempt
      404:
        description: Camera not found
    """
    data = request.get_json() or {}
    
    identifier = data.get('identifier')
    status_str = data.get('status') 

    if not identifier and not status_str:
        return jsonify({
            "success": False,
            "error": "At least one field (identifier or status) is required"
        }), 400
    try:
        camera = Camera.query.get_or_404(camera_id)
        #all validation should be considered in FE
        if identifier:
            identifier = identifier.strip()

            if len(identifier) < 3:
                return jsonify({
                    "success": False,
                    "error": "Identifier must be at least 3 characters long"
                }), 400

            if len(identifier) > 50:
                return jsonify({
                    "success": False,
                    "error": "Identifier is too long (maximum 50 characters)"
                }), 400

            if not re.match(r'^[a-zA-Z0-9\-_]+$', identifier):
                return jsonify({
                    "success": False,
                    "error": "Identifier can only contain letters, numbers, hyphens (-) and underscores (_)"
                }), 400
            camera.identifier = identifier

        if status_str:
            try:
                new_status = CameraStatus[status_str.upper()]

                if new_status == CameraStatus.RENTED:
                        return jsonify({
                            "success": False,
                            "error": "Cannot manually set status to RENTED. Please use the Rental service."
                        }), 400
                camera.status = new_status
            except KeyError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid status '{status_str}'. Valid options: {[s.name for s in CameraStatus]}"
                }), 400

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Camera updated successfully",
            "camera": {
                "id": camera.id,
                "identifier": camera.identifier,
                "product_id": camera.product_id,
                "status": camera.status,
                "product_name": camera.product.name if camera.product else None
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Failed to update camera: {str(e)}"
        }), 500
    
@cameras_bp.route('/cameras/<int:camera_id>', methods=['DELETE'])
@jwt_required()
def delete_camera(camera_id):
    """
    Delete a camera instance
    ---
    tags:
      - Cameras
    security:
      - cookieAuth: []
    parameters:
      - name: camera_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Camera deleted successfully
      400:
        description: Cannot delete camera (status is not AVAILABLE)
      404:
        description: Camera not found
    """

    try:
        camera = Camera.query.get(camera_id)
        if not camera:
            return jsonify({
                "success": False,
                "error": f"Camera with id {camera_id} not found"
            }), 404

        if camera.status != CameraStatus.AVAILABLE:
            return jsonify({
                "success": False,
                "error": "Cannot delete camera that is renting or maintaining"
            }), 400

        db.session.delete(camera)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Camera with id {camera_id} deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Failed to delete camera: {str(e)}"
        }), 500
    
@cameras_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_cameras():
    """
    Get a list of cameras with filtering and pagination
    ---
    tags:
      - Cameras
    security:
      - cookieAuth: []
    parameters:
      - name: status
        in: query
        type: string
        description: Filter by CameraStatus (e.g., AVAILABLE, MAINTENANCE)
      - name: product_id
        in: query
        type: integer
        description: Filter by Product ID
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 10
    responses:
      200:
        description: Paginated camera data
        schema:
          properties:
            success: {type: boolean}
            data:
              type: object
              properties:
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      id: {type: integer}
                      identifier: {type: string}
                      status: {type: string}
                      product_id: {type: integer}
                      product_name: {type: string}
                meta:
                  type: object
                  properties:
                    total_items: {type: integer}
                    total_pages: {type: integer}
                    current_page: {type: integer}
    """
    try:
        status_str = request.args.get('status')
        product_id = request.args.get('product_id')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        query = Camera.query.options(joinedload(Camera.product))
        if status_str:
            try:
                status_enum = CameraStatus[status_str.upper()]
                query = query.filter_by(status=status_enum)
            except KeyError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid status '{status_str}'. Valid options: {[s.name for s in CameraStatus]}"
                }), 400

        if product_id:
            if not product_id.isdigit():
                return jsonify({"success": False, "error": "product_id must be an integer"}), 400
            query = query.filter(Camera.product_id == int(product_id))

        # error_out=False means if the user asks for page 100 and there are only 2, return empty list
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            "success": True,
            "data": {
                "items": [{
                    "id": c.id,
                    "identifier": c.identifier,
                    "status": c.status.name,
                    "product_id": c.product_id,
                    "product_name": c.product.name if c.product else "Unknown"
                } for c in pagination.items],
                "meta": {
                    "total_items": pagination.total,
                    "total_pages": pagination.pages,
                    "current_page": pagination.page,
                    "per_page": pagination.per_page,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev
                }
            }
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to fetch cameras: {str(e)}"
        }), 500