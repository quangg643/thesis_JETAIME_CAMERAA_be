from datetime import time
from sqlalchemy.exc import IntegrityError
from app import create_app, db
from app.models import Shift



def seed_shifts():
    """
    Safely seed initial structural shifts into the database.
    Wrapped in try-except to gracefully handle pre-existing records.
    """
    print("Initializing structural shift data seeding...")
    
    # 1. Define standard operational shift rules using your model definitions
    morning = Shift(shift_name="morning", start_time=time(8, 0), end_time=time(12, 0), hours=4)
    afternoon = Shift(shift_name="afternoon", start_time=time(12, 0), end_time=time(17, 0), hours=5)
    evening = Shift(shift_name="evening", start_time=time(17, 0), end_time=time(22, 0), hours=5)
    night = Shift(shift_name="night", start_time=time(22, 0), end_time=time(4, 0), hours=6)

    try:
        # 2. Stage records for initialization
        db.session.add_all([morning, afternoon, evening, night])
        
        # 3. Attempt database execution write
        db.session.commit()
        print("Success: Shift structural baselines safely seeded into the database.")
        
    except IntegrityError as e:
        # Triggers if unique constraints are hit (e.g. shift_name already exists)
        db.session.rollback()
        print("Notice: Unique constraint hit. Shift structural data has already been seeded.")
        print(f"Details: {str(e.orig)}")
        
    except Exception as e:
        # Handles any fallback anomalies safely (missing columns, connection faults, etc.)
        db.session.rollback()
        print(f"Critical Error: Failed to commit seeds due to an unhandled exception: {str(e)}")
        
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_shifts()