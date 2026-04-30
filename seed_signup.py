import uuid
from app import db, create_app
from app.enums import GenderEnum, UserRole
from app.models import Employee
from werkzeug.security import generate_password_hash

app = create_app()

def seed_staff_batch():
    base_password = "06042003"
    hashed_password = generate_password_hash(base_password)
    
    # Sample names
    first_names = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Vu", "Phan", "Dinh", "Dang", "Bui"]
    last_names = ["An", "Binh", "Chi", "Dung", "Em", "Giang", "Hung", "Hoa", "Khanh", "Linh"]

    with app.app_context():
        print("🚀 Starting Batch Staff + Admin & Manager Seeding...")

        # === 1. Create Admin Account ===
        admin_name = "Admin System"
        admin_email = "admin@gmail.com"
        
        if not Employee.query.filter_by(email=admin_email).first():
            admin = Employee(
                name=admin_name,
                email=admin_email,
                gender=GenderEnum.MALE,
                password=hashed_password,
                role=UserRole.ADMIN,
                phone="0987654321",
                hour_salary=None,
                base_salary=15000000  # Example base salary for admin
            )
            db.session.add(admin)
            print(f"➕ Added Admin: {admin_name} | Email: {admin_email}")
        else:
            print(f"⚠️ Admin account with email {admin_email} already exists.")

        # === 2. Create Manager Account ===
        manager_name = "Manager Nguyen Van A"
        manager_email = "manager@gmail.com"
        
        if not Employee.query.filter_by(email=manager_email).first():
            manager = Employee(
                name=manager_name,
                email=manager_email,
                gender=GenderEnum.MALE,
                password=hashed_password,
                role=UserRole.MANAGER,
                phone="0987654322",
                hour_salary=None,
                base_salary=12000000  # Example base salary for manager
            )
            db.session.add(manager)
            print(f"➕ Added Manager: {manager_name} | Email: {manager_email}")
        else:
            print(f"⚠️ Manager account with email {manager_email} already exists.")

        # === 3. Create Staff Batch ===
        groups = [
            {"role": UserRole.STAFF_ON, "count": 10, "hour_salary": 50000, "gender": GenderEnum.MALE},
            {"role": UserRole.STAFF_OFF, "count": 10, "hour_salary": 45000, "gender": GenderEnum.FEMALE}
        ]

        total_created = 0

        for group in groups:
            role = group["role"]
            suffix = "On" if role == UserRole.STAFF_ON else "Off"
            
            for i in range(1, group["count"] + 1):
                name = f"{first_names[i-1]} {last_names[i-1]} ({suffix}-{i})"
                email = f"staff_{role.value.lower()}_{i}@gmail.com"

                # Check for duplicates
                if Employee.query.filter_by(email=email).first() or \
                   Employee.query.filter_by(name=name).first():
                    print(f"⚠️ Skipping {name} - already exists.")
                    continue

                new_user = Employee(
                    name=name,
                    email=email,
                    gender=group["gender"],
                    password=hashed_password,
                    role=role,
                    phone=f"09876543{i:02d}{'1' if suffix=='On' else '2'}",
                    hour_salary=group["hour_salary"],
                    base_salary=None
                )

                db.session.add(new_user)
                total_created += 1
                print(f"➕ Added Staff: {name} | Email: {email}")

        db.session.commit()
        print(f"\n🎉 Seeding completed! Created {total_created} staff members + 1 Admin + 1 Manager.")

if __name__ == "__main__":
    seed_staff_batch()