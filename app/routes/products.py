from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.enums import CameraStatus
from app.models import Camera, Product


products_bp = Blueprint('products', __name__)

@products_bp.route('/', methods=['POST'])
@jwt_required()
def add_product():
    """
    Add a new product with full pricing details
    ---
    tags:
      - Products
    security:
      - cookieAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          id: ProductInput
          required:
            - name
            - brand
          properties:
            name:
              type: string
              example: "Sony A7IV"
            brand:
              type: string
              example: "Sony"
            six_hour_price: {type: integer, default: 0}
            one_day_price: {type: integer, default: 0}
            two_day_price: {type: integer, default: 0}
            three_day_price: {type: integer, default: 0}
            additional_day_price: {type: integer, default: 0}
            additional_hour_price: {type: integer, default: 0}
            description: {type: string, default: ""}
    responses:
      201:
        description: Product created successfully along with computed stock profiles
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            product:
              type: object
              properties:
                id: {type: integer}
                name: {type: string}
                brand: {type: string}
                six_hour_price: {type: integer}
                one_day_price: {type: integer}
                two_day_price: {type: integer}
                three_day_price: {type: integer}
                additional_day_price: {type: integer}
                additional_hour_price: {type: integer}
                description: {type: string}
                total_stock: {type: integer, example: 0}
                available_stock: {type: integer, example: 0}
                rented_stock: {type: integer, example: 0}
                maintenance_stock: {type: integer, example: 0}
                created_at: {type: string, format: date-time}
      400:
        description: Bad request / validation error
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Missing JSON request body"}), 400

    name = data.get('name')
    brand = data.get('brand')
    
    six_hour_price = data.get('six_hour_price', 0)
    one_day_price = data.get('one_day_price', 0)
    two_day_price = data.get('two_day_price', 0)
    three_day_price = data.get('three_day_price', 0)
    additional_day_price = data.get('additional_day_price', 0)
    additional_hour_price = data.get('additional_hour_price', 0)
    description = data.get('description')
    
    if not name and not brand:
        return jsonify({"error": "name and brand are required"}), 400
    
    try:
        new_product = Product(
            name=name,
            brand=brand,
            six_hour_price=six_hour_price,
            one_day_price=one_day_price,
            two_day_price=two_day_price,
            three_day_price=three_day_price,
            additional_day_price=additional_day_price,
            additional_hour_price=additional_hour_price,
            description=description
        )

        db.session.add(new_product)
        db.session.commit()

        return jsonify({
            "message": "New product created successfully",
            "product_id": new_product.id,
            "name": new_product.name,
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Failed to add new camera product: {str(e)}"
        }), 500

@products_bp.route('/<int:product_id>', methods=['PUT'])
@jwt_required()
def update_product(product_id):
    """
    Update product pricing via query parameters
    ---
    tags:
      - Products
    security:
      - cookieAuth: []
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
      - name: six_hour_price
        in: query
        type: integer
      - name: one_day_price
        in: query
        type: integer
      - name: two_day_price
        in: query
        type: integer
      - name: three_day_price
        in: query
        type: integer
      - name: additional_day_price
        in: query
        type: integer
      - name: additional_hour_price
        in: query
        type: integer
    responses:
      200:
        description: Product updated successfully
      404:
        description: Product not found
    """
    product = Product.query.get_or_404(product_id)

    six_hour_price = request.args.get('six_hour_price', type=int)
    one_day_price = request.args.get('one_day_price', type=int)
    three_day_price = request.args.get('three_day_price', type=int)
    two_day_price = request.args.get('two_day_price', type=int)
    additional_day_price = request.args.get('additional_day_price', type=int)
    additional_hour_price = request.args.get('additional_hour_price', type=int)
    description = request.args.get('description', type=str)


    if six_hour_price is not None:
        product.six_hour_price = six_hour_price
    if one_day_price is not None:
        product.one_day_price = one_day_price
    if two_day_price is not None:
        product.two_day_price = two_day_price
    if three_day_price is not None:
        product.three_day_price = three_day_price
    if additional_day_price is not None:
        product.additional_day_price = additional_day_price
    if additional_hour_price is not None:
        product.additional_hour_price = additional_hour_price
    if description is not None:
      product.description = description

    db.session.commit()

    return jsonify({
        "message": "Product updated successfully",
        "product_id": product.id,
        "name": product.name
    }), 200

@products_bp.route('/<int:product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    """
    Delete a product template
    ---
    tags:
      - Products
    security:
      - cookieAuth: []
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Product deleted successfully
      404:
        description: Product not found
      500:
        description: Database error (e.g., if cameras are still linked to this product)
    """
    product = Product.query.get(product_id)
    if not product:
        return jsonify({
            "success": False,
            "error": "Camera category not found."
        }), 404

    # 2. Check if there are any associated cameras that are NOT available
    # Uses CameraStatus.AVAILABLE from your app.enums import structure
    non_available_cameras_count = Camera.query.filter(
        Camera.product_id == product_id,
        Camera.status != CameraStatus.AVAILABLE
    ).count()

    if non_available_cameras_count > 0:
        return jsonify({
            "success": False,
            "error": f"Cannot delete this category. There are currently {non_available_cameras_count} camera asset(s) that are rented out or in maintenance."
        }), 400

    try:
        # 3. Safe to cascade delete or remove remaining available cameras if any exist
        # If your database models don't have passive_deletes/cascades configured, 
        # explicitly remove the available camera assets first to avoid foreign key violations:
        Camera.query.filter_by(product_id=product_id).delete()

        # 4. Remove the core category template
        db.session.delete(product)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Camera category template and its available camera assets were deleted successfully."
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": "An internal database error occurred while trying to process the deletion request."
        }), 500
    

@products_bp.route('/', methods=['GET'])
@jwt_required()
def get_products_with_stock():
    """
    Get all product templates with distinct breakdown of status stock counts
    ---
    tags:
      - Products
    security:
      - cookieAuth: []
    responses:
      200:
        description: List of products with total, available, rented, and maintenance stock
        schema:
          type: object
          properties:
            success: {type: boolean}
            products:
              type: array
              items:
                type: object
                properties:
                  id: {type: integer}
                  name: {type: string}
                  brand: {type: string}
                  six_hour_price: {type: integer}
                  one_day_price: {type: integer}
                  two_day_price: {type: integer}
                  three_day_price: {type: integer}
                  additional_day_price: {type: integer}
                  additional_hour_price: {type: integer}
                  total_stock: {type: integer}
                  available_stock: {type: integer}
                  rented_stock: {type: integer}
                  maintenance_stock: {type: integer}
    """
    try:
        products = Product.query.all()
        
        result = []
        for product in products:
            # Query individual counts matching each dynamic CameraStatus assignment
            total_stock = Camera.query.filter_by(product_id=product.id).count()
            
            available_stock = Camera.query.filter_by(
                product_id=product.id,
                status=CameraStatus.AVAILABLE
            ).count()

            rented_stock = Camera.query.filter_by(
                product_id=product.id,
                status=CameraStatus.RENTED
            ).count()

            maintenance_stock = Camera.query.filter_by(
                product_id=product.id,
                status=CameraStatus.MAINTENANCE
            ).count()

            product_data = {
                "id": product.id,
                "name": product.name,
                "brand": product.brand.value if product.brand else None,
                "six_hour_price": product.six_hour_price,
                "one_day_price": product.one_day_price,
                "two_day_price": product.two_day_price,
                "three_day_price": product.three_day_price,
                "additional_day_price": product.additional_day_price,
                "additional_hour_price": product.additional_hour_price,
                "description": product.description or "N/A",
                "total_stock": total_stock,
                "available_stock": available_stock,
                "rented_stock": rented_stock,
                "maintenance_stock": maintenance_stock,
                "created_at": product.created_at.isoformat()
            }
            result.append(product_data)

        return jsonify({
            "success": True,
            "products": result
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500