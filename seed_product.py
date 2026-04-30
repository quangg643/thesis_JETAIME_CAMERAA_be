from app import create_app, db
from app.models import Product


def seed_products():
    products_data = [
        Product(
            name="Fujifilm XM5",
            brand="Fujifilm",
            six_hour_price=150000,
            one_day_price=230000,
            two_day_price=450000,
            three_day_price=610000,
            additional_day_price=200000,
            additional_hour_price=40000,
        ),
        Product(
            name="Fujifilm X-T100",
            brand="Fujifilm",
            six_hour_price=100000,
            one_day_price=160000,
            two_day_price=280000,
            three_day_price=420000,
            additional_day_price=120000,
            additional_hour_price=20000,
        ),
        Product(
            name="Fujifilm X-A5",
            brand="Fujifilm",
            six_hour_price=100000,
            one_day_price=150000,
            two_day_price=280000,
            three_day_price=410000,
            additional_day_price=100000,
            additional_hour_price=20000,
        ),
        Product(
            name="Canon R-50",
            brand="Canon",
            six_hour_price=140000,
            one_day_price=200000,
            two_day_price=390000,
            three_day_price=570000,
            additional_day_price=160000,
            additional_hour_price=30000,
        ),
        Product(
            name="Canon M50",
            brand="Canon",
            six_hour_price=100000,
            one_day_price=150000,
            two_day_price=280000,
            three_day_price=410000,
            additional_day_price=120000,
            additional_hour_price=20000,
        ),
        Product(
            name="Canon M100",
            brand="Canon",
            six_hour_price=100000,
            one_day_price=140000,
            two_day_price=260000,
            three_day_price=380000,
            additional_day_price=120000,
            additional_hour_price=20000,
        ),
        Product(
            name="Canon M10",
            brand="Canon",
            six_hour_price=100000,
            one_day_price=140000,
            two_day_price=260000,
            three_day_price=380000,
            additional_day_price=120000,
            additional_hour_price=20000,
        ),
        Product(
            name="Sony ZV-E10",
            brand="Sony",
            six_hour_price=100000,
            one_day_price=170000,
            two_day_price=330000,
            three_day_price=480000,
            additional_day_price=150000,
            additional_hour_price=20000,
        ),
        Product(
            name="Casio EX-JE10",
            brand="Casio",
            six_hour_price=80000,
            one_day_price=120000,
            two_day_price=230000,
            three_day_price=330000,
            additional_day_price=100000,
            additional_hour_price=20000,
        ),
        Product(
            name="Fujifilm X-S10",
            brand="Fujifilm",
            six_hour_price=250000,
            one_day_price=380000,
            two_day_price=750000,
            three_day_price=1110000,
            additional_day_price=330000,
            additional_hour_price=40000,
        ),
        Product(
            name="Fujifilm X-T20",
            brand="Fujifilm",
            six_hour_price=140000,
            one_day_price=220000,
            two_day_price=430000,
            three_day_price=600000,
            additional_day_price=190000,
            additional_hour_price=30000,
        ),
    ]

    db.session.bulk_save_objects(products_data)
    db.session.commit()
    print(f"✅ Seeded {len(products_data)} products successfully!")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_products()