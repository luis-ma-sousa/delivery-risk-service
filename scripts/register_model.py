"""Train a model on all usable data and register it in MLflow.

Run from the repository root:

    uv run python scripts/register_model.py
"""

import mlflow

from delivery_risk.database import get_session
from delivery_risk.features import build_training_features
from delivery_risk.training import train_and_register, usable_orders


def main() -> None:
    mlflow.set_experiment("delivery-risk-production")

    with get_session() as session:
        features = usable_orders(build_training_features(session))

    run_id = train_and_register(features)
    print(f"registered run: {run_id}")


if __name__ == "__main__":
    main()
