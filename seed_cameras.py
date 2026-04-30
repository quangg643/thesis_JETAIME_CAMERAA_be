# seeds/seed_cameras.py
from app import create_app, db
from datetime import datetime

from app.enums import CameraStatus
from app.models import Camera, Product

def seed_cameras_only():
    """Seed 5 camera units for each existing Product"""
    print("🌱 Starting Camera Seeding (5 units per product)...\n")

    added = 0
    skipped = 0

    for product_id in range(1, 12):   # Product IDs from 1 to 11
        # Get product name for better identifier
        product = Product.query.get(product_id)

        if not product:
            print(f"⚠️  Product ID {product_id} not found. Skipping...")
            continue

        # Clean product name for identifier
        base_name = product.name.replace(" ", "-").replace("'", "").upper()

        for i in range(1, 6):   # Create 5 cameras
            identifier = f"{base_name}-{i:02d}"

            # Check if camera already exists
            existing = Camera.query.filter_by(identifier=identifier).first()
            if existing:
                print(f"⏭️  Skipped (already exists): {identifier}")
                skipped += 1
                continue

            # Create new camera
            camera = Camera(
                identifier=identifier,
                product_id=product_id,
                status=CameraStatus.AVAILABLE
            )

            db.session.add(camera)
            added += 1
            print(f"✅ Added: {identifier}  →  {product.name}")

    try:
        db.session.commit()
        print("\n" + "="*75)
        print("🎉 CAMERA TABLE SEEDING COMPLETED!")
        print(f"   Added   : {added} cameras")
        print(f"   Skipped : {skipped} duplicates")
        print(f"   Total Cameras in DB: {Camera.query.count()}")
        print("="*75)
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error while seeding cameras: {e}")


# Run the script
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_cameras_only()