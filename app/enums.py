from enum import Enum

class UserRole(str, Enum):
    STAFF_ON = "STAFF_ON"
    STAFF_OFF = "STAFF_OFF"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"

class GenderEnum(str, Enum):
    MALE = "male"
    FEMALE = "female"

class AccountStatus(str, Enum):
    ACTIVE = "active"
    OFFBOARDED = "offboarded"

class CameraStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    RENTED = "rented"
    MAINTENANCE = "maintenance"

class CameraBrand(str, Enum):
    CASIO = "Casio"
    FUJIFILM = "Fujifilm"
    CANON = "Canon"
    SONY = "Sony"

class PaymentEnum(str, Enum):
    PAID = "paid"
    WAITING = "waiting"
    PENDING = "pending"

class RentalStatus(str, Enum):
    PENDING_PICKUP = "pending pickup"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"