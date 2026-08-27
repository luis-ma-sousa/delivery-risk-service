"""Tests that exercise the full path, including the database.

Unlike test_api.py, these need a populated `curated` schema: the endpoint
resolves coordinates on every request (ADR 0015).
"""

from fastapi.testclient import TestClient

from delivery_risk.api.app import app

client = TestClient(app)

VALID_REQUEST = {
    "purchase_timestamp": "2018-03-15T14:30:00-03:00",
    "estimated_delivery_date": "2018-03-28T00:00:00-03:00",
    "customer_zip_code_prefix": "01001",
    "payments": [{"payment_type": "boleto", "installments": 1, "value": 129.90}],
    "items": [
        {
            "product_id": "abc123",
            "seller_id": "3442f8959a84dea7ee197c632cb2df15",
            "price": 109.90,
            "freight_value": 20.00,
        }
    ],
}


def test_predict_returns_a_probability() -> None:
    response = client.post("/predict", json=VALID_REQUEST)

    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["probability_late"] <= 1.0
    assert body["model_version"] == "constant-0.1.0"


def test_predict_accepts_several_payments() -> None:
    request = VALID_REQUEST | {
        "payments": [
            {"payment_type": "voucher", "installments": 1, "value": 29.90},
            {"payment_type": "credit_card", "installments": 3, "value": 100.00},
        ]
    }

    response = client.post("/predict", json=request)

    assert response.status_code == 200


def test_predict_accepts_offsets_from_different_timezones() -> None:
    request = VALID_REQUEST | {
        "purchase_timestamp": "2018-03-15T14:30:00-03:00",
        "estimated_delivery_date": "2018-03-28T00:00:00Z",
    }

    response = client.post("/predict", json=request)

    assert response.status_code == 200
