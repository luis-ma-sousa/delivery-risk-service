"""Tests for the prediction interface and its implementations."""

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from delivery_risk.prediction import ConstantModel, RiskModel, TrainedModel
from delivery_risk.training import FEATURE_COLUMNS


def write_model(directory: Path) -> None:
    """Write a model trained on noise, in the format TrainedModel expects.

    The model itself is meaningless; what is under test is whether
    TrainedModel loads it, orders the features as the metadata says, and
    answers with a probability.
    """
    rng = np.random.default_rng(0)
    x = rng.random((200, len(FEATURE_COLUMNS)))
    y = rng.random(200) > 0.9

    pipeline = Pipeline([("scale", StandardScaler()), ("model", LogisticRegression(max_iter=1000))])
    pipeline.fit(x, y)

    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, directory / "model.joblib")
    (directory / "model.json").write_text(
        json.dumps(
            {
                "columns": FEATURE_COLUMNS,
                "medians": {
                    "distance_km": 500.0,
                    "total_weight_g": 2000.0,
                    "total_volume_cm3": 10000.0,
                },
                "trained_through": "2018-08-29",
            }
        )
    )


def test_constant_model_satisfies_the_protocol() -> None:
    assert isinstance(ConstantModel(), RiskModel)


def test_trained_model_satisfies_the_protocol(tmp_path: Path) -> None:
    write_model(tmp_path)

    assert isinstance(TrainedModel(tmp_path), RiskModel)


def test_trained_model_returns_a_probability(tmp_path: Path) -> None:
    write_model(tmp_path)
    model = TrainedModel(tmp_path)

    features: dict[str, float | str | None] = {
        "distance_km": 300.0,
        "estimated_slack_days": 12.0,
        "item_count": 1.0,
        "total_freight": 20.0,
        "total_price": 100.0,
        "total_weight_g": 500.0,
        "total_volume_cm3": 3000.0,
        "purchase_day_of_week": 3.0,
        "purchase_hour": 14.0,
        "customer_state": "SP",
        "origin_state": "SP",
    }

    probability = model.predict_probability(features)

    assert isinstance(probability, float)
    assert 0.0 <= probability <= 1.0


def test_trained_model_imputes_a_missing_feature(tmp_path: Path) -> None:
    """A null distance is filled with the recorded median, not left as None.

    The model would reject a None outright, so the imputation happening here
    rather than crashing is the behaviour worth asserting.
    """
    write_model(tmp_path)
    model = TrainedModel(tmp_path)

    features: dict[str, float | str | None] = {
        "distance_km": None,
        "estimated_slack_days": 12.0,
        "item_count": 1.0,
        "total_freight": 20.0,
        "total_price": 100.0,
        "total_weight_g": 500.0,
        "total_volume_cm3": 3000.0,
        "purchase_day_of_week": 3.0,
        "purchase_hour": 14.0,
        "customer_state": "SP",
        "origin_state": "SP",
    }

    probability = model.predict_probability(features)

    assert 0.0 <= probability <= 1.0


def test_trained_model_reports_when_it_was_trained(tmp_path: Path) -> None:
    write_model(tmp_path)

    assert TrainedModel(tmp_path).version == "logistic-2018-08-29"
