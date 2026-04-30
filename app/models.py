from datetime import datetime, date, timezone
from app import db
from sqlalchemy import Enum as SQLEnum

from app.enums import AccountStatus, CameraBrand, CameraStatus, GenderEnum, PaymentEnum, RentalStatus, UserRole
from app.helpers import get_vietnam_time

class TokenBlocklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    gender = db.Column(SQLEnum(GenderEnum), nullable=False)
    
    role = db.Column(SQLEnum(UserRole), nullable=False)
    
    
    password = db.Column(db.String(255), nullable=False)
    base_salary = db.Column(db.Integer, default=0)
    hour_salary = db.Column(db.Integer, default=0)

    status = db.Column(SQLEnum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE)
    
    offboard_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=get_vietnam_time)

    shifts = db.relationship(
        'Shift',
        secondary='shift_assigned',
        back_populates='employees', 
        viewonly=True
    )   

    shift_assignments = db.relationship(
        'ShiftAssigned',
        back_populates='employee',
        cascade='all, delete-orphan'
    )

    rentals = db.relationship('Rental', backref='employee', lazy='joined', cascade='all, delete-orphan')
    payroll = db.relationship('Payroll', backref='employee', lazy=True, cascade='all, delete-orphan')
    penalty = db.relationship('Penalty', backref='employee', lazy='dynamic', cascade='all, delete-orphan')

class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    identifier = db.Column(db.String(50), unique=True, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    
    status = db.Column(SQLEnum(CameraStatus), default=CameraStatus.AVAILABLE, nullable=False)
    
    created_at = db.Column(db.DateTime, default=get_vietnam_time)
    updated_at = db.Column(db.DateTime, default=get_vietnam_time, onupdate=get_vietnam_time)

    product = db.relationship('Product', back_populates='cameras', lazy='joined')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(100), nullable=False, unique=True)
    brand = db.Column(SQLEnum(CameraBrand), nullable=False)
    
    six_hour_price = db.Column(db.Integer)
    one_day_price = db.Column(db.Integer)
    two_day_price = db.Column(db.Integer)
    three_day_price = db.Column(db.Integer)
    additional_day_price = db.Column(db.Integer)
    
    additional_hour_price = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=get_vietnam_time)
    cameras = db.relationship('Camera', back_populates='product', lazy=True)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True)
    gender = db.Column(SQLEnum(GenderEnum), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=get_vietnam_time)

class Rental(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    camera_id = db.Column(db.Integer, db.ForeignKey('camera.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    
    start_time = db.Column(db.DateTime, nullable=False)
    expected_return_time = db.Column(db.DateTime, nullable=False)
    actual_return_date = db.Column(db.DateTime, nullable=True)
    
    rental_fee = db.Column(db.Integer)
    penalty_fee = db.Column(db.Integer, default=0)
    total_amount = db.Column(db.Integer)
    payment_status = db.Column(SQLEnum(PaymentEnum), nullable=False)
    
    deposit_amount = db.Column(db.Integer, nullable=False)
    deposit_method = db.Column(db.String(50))
    deposit_status = db.Column(db.String(20), default=PaymentEnum.PAID)

    note = db.Column(db.String, nullable=True)
    
    status = db.Column(SQLEnum(RentalStatus), nullable=False)

    created_at = db.Column(db.DateTime, default=get_vietnam_time)

    customer = db.relationship('Customer', backref='rentals')
    camera = db.relationship('Camera', backref='rentals')
class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    
    hours = db.Column(db.Integer, nullable=False)

    shift_assignments = db.relationship(
        'ShiftAssigned',
        back_populates='shift',
        cascade='all, delete-orphan'
    )

    employees = db.relationship(
        'Employee',
        secondary='shift_assigned',
        back_populates='shifts',
        viewonly=True
    )
class ShiftAssigned(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)
    assigned_date = db.Column(db.Date, nullable=False)
    
    created_at = db.Column(db.DateTime, default=get_vietnam_time)

    employee = db.relationship('Employee', back_populates='shift_assignments')
    shift = db.relationship('Shift', back_populates='shift_assignments')

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'shift_id', 'assigned_date', name='_emp_shift_date_uc'),
    )
class Kpi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    shift_assigned_id = db.Column(db.Integer, db.ForeignKey('shift_assigned.id'), nullable=True)
    no_customer = db.Column(db.Integer, nullable = True)
    
    created_at = db.Column(db.DateTime, default=get_vietnam_time)

class Penalty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    
    penalty_name = db.Column(db.Text, nullable=False)
    level = db.Column(db.Integer, nullable=False)
    count = db.Column(db.Integer, default=1, nullable=False)
    
    created_at = db.Column(db.DateTime, default=get_vietnam_time)

class Payroll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    period = db.Column(db.String(7), nullable=False)
    bonus = db.Column(db.Integer, default=0)
    total_pay = db.Column(db.Integer, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=get_vietnam_time)