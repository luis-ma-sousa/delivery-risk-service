"""Feature extraction against a real database."""

import polars as pl

from delivery_risk.api.schemas import PredictionRequest
from delivery_risk.database import get_session
from delivery_risk.features import build_features, build_training_features


def test_build_features_produces_every_feature(postgres_url: str) -> None:
    request = PredictionRequest(
        purchase_timestamp="2018-03-15T14:30:00-03:00",
        estimated_delivery_date="2018-03-28T00:00:00-03:00",
        customer_zip_code_prefix="01001",
        payments=[{"payment_type": "boleto", "installments": 1, "value": 129.90}],
        customer_state="SP",
        items=[
            {
                "product_id": "product-with-attributes",
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
        "total_weight_g",
        "total_volume_cm3",
        "purchase_day_of_week",
        "purchase_hour",
        "customer_state",
        "origin_state",
    }
    assert features["distance_km"] is not None
    assert 84 < features["distance_km"] < 86
    assert features["estimated_slack_days"] == 12.395833333333334
    assert features["item_count"] == 1.0
    assert features["total_freight"] == 20.0
    assert features["total_price"] == 100.0
    assert features["purchase_day_of_week"] == 3.0
    assert features["purchase_hour"] == 14.0
    assert features["total_weight_g"] == 500.0
    assert features["total_volume_cm3"] == 3000.0
    assert features["customer_state"] == "SP"
    assert features["origin_state"] == "SP"


def test_purchase_timing_does_not_depend_on_the_offset_sent(postgres_url: str) -> None:
    """The same instant in two offsets must produce the same timing features.

    14:30 in São Paulo and 17:30 UTC are the same moment. A caller elsewhere
    would otherwise shift the order into a different hour and possibly a
    different day.
    """
    items = [
        {
            "product_id": "product-with-attributes",
            "seller_id": "seller-with-location",
            "price": 100.00,
            "freight_value": 20.00,
        }
    ]
    payments = [{"payment_type": "boleto", "installments": 1, "value": 129.90}]

    in_sao_paulo = PredictionRequest(
        purchase_timestamp="2018-03-15T14:30:00-03:00",
        estimated_delivery_date="2018-03-28T00:00:00-03:00",
        customer_zip_code_prefix="01001",
        customer_state="SP",
        payments=payments,
        items=items,
    )
    in_utc = PredictionRequest(
        purchase_timestamp="2018-03-15T17:30:00Z",
        estimated_delivery_date="2018-03-28T03:00:00Z",
        customer_zip_code_prefix="01001",
        customer_state="SP",
        payments=payments,
        items=items,
    )

    with get_session() as session:
        local = build_features(session, in_sao_paulo)
        utc = build_features(session, in_utc)

    assert local["purchase_hour"] == utc["purchase_hour"] == 14.0
    assert local["purchase_day_of_week"] == utc["purchase_day_of_week"] == 3.0
    assert local["estimated_slack_days"] == utc["estimated_slack_days"]


def test_batch_and_per_request_features_agree(postgres_url: str) -> None:
    """The two feature implementations must produce the same values.

    Training reads features in bulk from SQL; the service computes them per
    request in Python. Nothing forces the two to agree, and if they drift the
    model is served inputs it was not trained on — a failure that shows up as
    degraded predictions rather than as an error.
    """
    request = PredictionRequest(
        purchase_timestamp="2018-03-15T14:30:00-03:00",
        estimated_delivery_date="2018-03-28T00:00:00-03:00",
        customer_zip_code_prefix="01001",
        customer_state="SP",
        payments=[{"payment_type": "boleto", "installments": 1, "value": 129.90}],
        items=[
            {
                "product_id": "product-with-attributes",
                "seller_id": "seller-with-location",
                "price": 100.00,
                "freight_value": 20.00,
            }
        ],
    )

    with get_session() as session:
        per_request = build_features(session, request)
        batch = build_training_features(session)

    row = batch.filter(pl.col("order_id") == "order-1").to_dicts()[0]

    for name, expected in per_request.items():
        actual = row[name]
        if isinstance(expected, float) and isinstance(actual, float):
            assert abs(actual - expected) < 1e-6, f"{name}: {actual} != {expected}"
        else:
            assert actual == expected, f"{name}: {actual} != {expected}"
