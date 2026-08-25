"""Transform `raw` into `curated`.

Run from the repository root, after the raw layer has been loaded:

    uv run python scripts/transform.py
"""

from delivery_risk.database import get_session
from delivery_risk.transformation import (
    transform_persons,
    transform_sellers,
    transform_zip_code_locations,
    transform_category_translation, 
    transform_products,
    transform_customers,
    transform_orders, 
    transform_order_items,
    transform_order_payments,
)

def main() -> None:
    with get_session() as session:
        transform_zip_code_locations(session)
        transform_persons(session)
        transform_category_translation(session)
        transform_sellers(session)
        transform_products(session)
        transform_customers(session)
        transform_orders(session)
        transform_order_items(session)
        transform_order_payments(session)
        session.commit()
    print("\ndone")


if __name__ == "__main__":
    main()