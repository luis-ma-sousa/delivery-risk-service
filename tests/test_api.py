"""Tests for the HTTP contract.

These run without a server and without a database: the endpoint depends on the
prediction protocol, not on either.
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
            "seller_id": "xyz789",
            "price": 109.90,
            "freight_value": 20.00,
        }
    ],
}


def test_health_reports_the_loaded_model() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["model_version"] == "constant-0.1.0"


def test_predict_returns_a_probability() -> None:
    response = client.post("/predict", json=VALID_REQUEST)

    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["probability_late"] <= 1.0
    assert body["model_version"] == "constant-0.1.0"


def test_predict_rejects_an_unknown_payment_type() -> None:
    request = VALID_REQUEST | {
        "payments": [{"payment_type": "dinheiro", "installments": 1, "value": 10}]
    }

    response = client.post("/predict", json=request)

    assert response.status_code == 422


def test_predict_accepts_several_payments() -> None:
    request = VALID_REQUEST | {
        "payments": [
            {"payment_type": "voucher", "installments": 1, "value": 29.90},
            {"payment_type": "credit_card", "installments": 3, "value": 100.00},
        ]
    }

    response = client.post("/predict", json=request)

    assert response.status_code == 200


def test_predict_rejects_an_order_with_no_items() -> None:
    request = VALID_REQUEST | {"items": []}

    response = client.post("/predict", json=request)

    assert response.status_code == 422


def test_predict_rejects_an_unknown_field() -> None:
    request = VALID_REQUEST | {"delivered_customer_date": "2018-03-20T00:00:00"}

    response = client.post("/predict", json=request)

    assert response.status_code == 422


def test_predict_rejects_an_estimate_before_the_purchase() -> None:
    request = VALID_REQUEST | {"estimated_delivery_date": "2018-03-01T00:00:00"}

    response = client.post("/predict", json=request)

    assert response.status_code == 422


def test_predict_rejects_a_naive_timestamp() -> None:
    request = VALID_REQUEST | {"purchase_timestamp": "2018-03-15T14:30:00"}

    response = client.post("/predict", json=request)

    assert response.status_code == 422


def test_predict_accepts_offsets_from_different_timezones() -> None:
    request = VALID_REQUEST | {
        "purchase_timestamp": "2018-03-15T14:30:00-03:00",
        "estimated_delivery_date": "2018-03-28T00:00:00Z",
    }

    response = client.post("/predict", json=request)

    assert response.status_code == 200
