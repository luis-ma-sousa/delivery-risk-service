"""Train a model on all usable data and write it to models/.

Run from the repository root:

    uv run python scripts/register_model.py
"""

from delivery_risk.database import get_session
from delivery_risk.features import build_training_features
from delivery_risk.training import train_and_save, usable_orders


def main() -> None:
    with get_session() as session:
        features = usable_orders(build_training_features(session))

    directory = train_and_save(features)
    print(f"model written to {directory}/")


if __name__ == "__main__":
    main()
