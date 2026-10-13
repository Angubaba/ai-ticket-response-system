from sqlalchemy import select

from .db import SessionLocal
from .models import FieldDefinition

DEFAULT_FIELDS = [
    dict(key="order_number", label="Order number", field_type="text", required=False, sort_order=1),
    dict(
        key="product",
        label="Product",
        field_type="dropdown",
        required=True,
        options=["Mobile app", "Web dashboard", "Smart device", "Subscription plan"],
        sort_order=2,
    ),
    dict(key="units_affected", label="Units affected", field_type="number", required=False, sort_order=3),
    dict(key="issue_date", label="Date issue first occurred", field_type="date", required=False, sort_order=4),
    dict(key="customer_verified", label="Customer identity verified", field_type="checkbox", required=False, sort_order=5),
]


def seed_default_fields() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(FieldDefinition).limit(1)) is None:
            db.add_all(FieldDefinition(**f) for f in DEFAULT_FIELDS)
            db.commit()
    finally:
        db.close()
