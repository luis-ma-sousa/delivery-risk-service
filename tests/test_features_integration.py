"""Feature extraction against a real database."""

from delivery_risk.api.schemas import PredictionRequest
from delivery_risk.database import get_session
from delivery_risk.features import build_features


def test_build_features_produces_every_feature(postgres_url: str) -> None:
    request = PredictionRequest(
        purchase_timestamp="2018-03-15T14:30:00-03:00",
        estimated_delivery_date="2018-03-28T00:00:00-03:00",
        customer_zip_code_prefix="01001",
        payments=[{"payment_type": "boleto", "installments": 1, "value": 129.90}],
        items=[
            {
                "product_id": "abc123",
                "seller_id": "seller-with-location",
                "price": 100.00,
                "freight_value": 20.00,
            }
        ],
    )

    with get_session() as session:
        features = build_features(session, request)

    assert set(features) == {
        "distance_km",
        "estimated_slack_days",
        "item_count",
        "total_freight",
        "total_price",
        "purchase_day_of_week",
        "purchase_hour",
    }
    assert features["distance_km"] is not None
    assert 84 < features["distance_km"] < 86
    assert features["estimated_slack_days"] == 12.395833333333334
    assert features["item_count"] == 1.0
    assert features["total_freight"] == 20.0
    assert features["total_price"] == 100.0
    assert features["purchase_day_of_week"] == 3.0
    assert features["purchase_hour"] == 14.0
