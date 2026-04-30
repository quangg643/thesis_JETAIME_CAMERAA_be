from app import create_app, db
from app.enums import GenderEnum
from app.helpers import get_vietnam_time
from app.models import Customer


def seed_customers():
    # List of sample data to make it look realistic
    names = [
        "Nguyen Van A", "Tran Thi B", "Le Van C", "Pham Thi D", "Hoang Van E",
        "Vo Thi F", "Dang Van G", "Bui Thi H", "Do Van I", "Ngo Thi K"
    ]
    
    emails = [f"user{i}@example.com" for i in range(1, 11)]
    
    # Example phone numbers
    phones = [f"09012345{i}" for i in range(0, 10)]
    
    # Alternating genders for variety
    genders = [
        GenderEnum.MALE, GenderEnum.FEMALE, GenderEnum.MALE, GenderEnum.FEMALE, GenderEnum.MALE,
        GenderEnum.FEMALE, GenderEnum.MALE, GenderEnum.FEMALE, GenderEnum.MALE, GenderEnum.FEMALE
    ]

    with app.app_context():
        print("Starting to seed customers...")
        
        for i in range(10):
            # Check if customer already exists to avoid Unique Constraint errors
            existing = Customer.query.filter_by(name=names[i]).first()
            if not existing:
                new_customer = Customer(
                    name=names[i],
                    email=emails[i],
                    gender=genders[i],
                    phone=phones[i],
                    address=f"{i+100} Le Loi Street, District 1, HCMC",
                    # created_at will use get_vietnam_time by default, 
                    # but you can pass it explicitly if you want to be sure
                    created_at=get_vietnam_time()
                )
                db.session.add(new_customer)
        
        try:
            db.session.commit()
            print("Successfully seeded 10 customers!")
        except Exception as e:
            db.session.rollback()
            print(f"Error seeding database: {e}")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_customers()