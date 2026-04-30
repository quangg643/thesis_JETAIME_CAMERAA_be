import os

from flask import Flask, jsonify
from flask_cors import CORS

from flasgger import Swagger

from app.config import Config
from app.extensions import db, jwt
from app.models import Employee, TokenBlocklist
from app.routes.employees import employees_bp
from app.routes.products import products_bp
from app.routes.auth import auth_bp
from app.routes.cameras import cameras_bp
from app.routes.customers import customers_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    Swagger(app)
    CORS(
        app,
        supports_credentials=True,
        origins=["http://127.0.0.1:5500", "https://localhost:5500"],
        allow_headers=["Content-Type", "X-CSRF-TOKEN"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data.get("sub")
        if identity is None:
            return None
        return Employee.query.get(int(identity))

    app.register_blueprint(employees_bp, url_prefix='/api/employees')
    app.register_blueprint(products_bp, url_prefix='/api/products')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(cameras_bp, url_prefix='/api/cameras')
    app.register_blueprint(customers_bp, url_prefix='/api/customers')


    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        token = db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar()
        return token is not None


    with app.app_context():
        db.create_all()

    return app