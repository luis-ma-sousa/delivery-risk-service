"""Train and score the model across a sequence of temporal cutoffs.

Run from the repository root:

    uv run python scripts/train.py

Each cutoff trains on everything before it and scores the month that follows.
Reading the months separately rather than as one test set is deliberate: the
late rate moves by a factor of fifteen across this period, and an average over
it would hide both the good months and the bad ones (ADR 0019).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import mlflow

from delivery_risk.database import get_session
from delivery_risk.features import build_training_features
from delivery_risk.training import run_experiment, usable_orders

SAO_PAULO = ZoneInfo("America/Sao_Paulo")

CUTOFFS = [
    (datetime(2018, 3, 1, tzinfo=SAO_PAULO), datetime(2018, 4, 1, tzinfo=SAO_PAULO)),
    (datetime(2018, 4, 1, tzinfo=SAO_PAULO), datetime(2018, 5, 1, tzinfo=SAO_PAULO)),
    (datetime(2018, 5, 1, tzinfo=SAO_PAULO), datetime(2018, 6, 1, tzinfo=SAO_PAULO)),
    (datetime(2018, 6, 1, tzinfo=SAO_PAULO), datetime(2018, 7, 1, tzinfo=SAO_PAULO)),
    (datetime(2018, 7, 1, tzinfo=SAO_PAULO), datetime(2018, 8, 1, tzinfo=SAO_PAULO)),
    (datetime(2018, 8, 1, tzinfo=SAO_PAULO), datetime(2018, 9, 1, tzinfo=SAO_PAULO)),
]


def main() -> None:
    mlflow.set_experiment("delivery-risk-baseline")

    with get_session() as session:
        features = usable_orders(build_training_features(session))

    print(
        f"{'window':<9} {'train':>7} {'test':>6} {'observed':>9} "
        f"{'predicted':>10} {'brier':>9} {'baseline':>9} {'auc':>6}"
    )

    for cutoff, window_end in CUTOFFS:
        result = run_experiment(features, cutoff, window_end)
        auc = f"{result.model.auc:.3f}" if result.model.auc is not None else "n/a"
        print(
            f"{cutoff.strftime('%Y-%m'):<9} "
            f"{result.train_orders:>7} "
            f"{result.test_orders:>6} "
            f"{result.model.observed_rate:>9.1%} "
            f"{result.model.mean_predicted:>10.1%} "
            f"{result.model.brier:>9.5f} "
            f"{result.baseline.brier:>9.5f} "
            f"{auc:>6}"
        )


if __name__ == "__main__":
    main()
