from datetime import datetime

import polars as pl

from delivery_risk.transformation import (
    within_brazil,
    without_contradictions,
)


def test_bounding_box() -> None:
    """Test that the bounding box is computed correctly."""
    # Create a DataFrame with known coordinates
    # São Paulo (-23.55, -43.63)
    # Braga (PT) (41.6, -8.4)
    df = pl.DataFrame({"latitude": [-23.55, 41.6], "longitude": [-43.63, -8.4]})

    inside = within_brazil(df, "latitude", "longitude")

    assert inside.height == 1, "Only São Paulo should be inside the bounding box"
    assert inside["latitude"][0] == -23.55
    assert inside["longitude"][0] == -43.63


def test_orders_without_contradictions() -> None:
    """Test that the without_contradictions function filters out contradictory orders."""
    df = pl.DataFrame(
        {
            "order_id": ["a", "b", "c", "d"],
            "status": ["delivered", "delivered", "shipped", "canceled"],
            "delivered_carrier_date": [
                datetime(2023, 1, 1),
                datetime(2023, 1, 2),
                datetime(2023, 1, 1),
                datetime(2023, 1, 1),
            ],
            "delivered_customer_date": [
                datetime(2023, 1, 5),  # a — valid order, kept
                datetime(2023, 1, 1),  # b — delivered before despatch, removed
                None,  # c — in transit, kept
                datetime(2023, 1, 5),  # d — cancelled with delivery, removed
            ],
        }
    )

    filtered = without_contradictions(df)

    assert filtered.height == 2, "Only two orders should remain after filtering"
    assert filtered["order_id"].to_list() == ["a", "c"]
