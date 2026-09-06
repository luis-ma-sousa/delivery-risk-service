"""Training data preparation.

Splits are temporal, never random. The late-delivery rate ranges from 1.4% to
21.4% across months of this dataset, so a random split would let the model see
orders from the same week it is being evaluated on, and learn a rate it could
not know in advance.
"""

from datetime import datetime
from typing import NamedTuple
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SAO_PAULO = ZoneInfo("America/Sao_Paulo")

USABLE_FROM = datetime(2017, 1, 1, tzinfo=SAO_PAULO)
USABLE_UNTIL = datetime(2018, 9, 1, tzinfo=SAO_PAULO)


class TemporalSplit(NamedTuple):
    """Orders before a cutoff, and orders in the window after it."""

    train: pl.DataFrame
    test: pl.DataFrame
    cutoff: datetime
    window_end: datetime


def usable_orders(features: pl.DataFrame) -> pl.DataFrame:
    """Restrict to the period where the data is dense and complete.

    The last months of 2016 hold 263 orders across four months, two of which
    have a single order each. September and October 2018 are absent to right
    censoring: orders placed then had not been delivered when the dataset was
    extracted, so what survives is biased toward fast deliveries.

    Timestamps are converted to São Paulo first, so that period boundaries
    mean what they say in the timezone the operation runs on (ADR 0018).
    """
    return (
        features.with_columns(
            pl.col("purchase_timestamp").dt.convert_time_zone("America/Sao_Paulo")
        )
        .filter(
            (pl.col("purchase_timestamp") >= USABLE_FROM)
            & (pl.col("purchase_timestamp") < USABLE_UNTIL)
        )
        .sort("purchase_timestamp")
    )


def split_at(features: pl.DataFrame, cutoff: datetime, window_end: datetime) -> TemporalSplit:
    """Train on everything before the cutoff, test on the window that follows.

    Both boundaries are given explicitly rather than derived from a month
    count: months are uneven, and the question being asked — how does the
    model do over these particular weeks — is clearer stated than inferred.
    """
    train = features.filter(pl.col("purchase_timestamp") < cutoff)
    test = features.filter(
        (pl.col("purchase_timestamp") >= cutoff) & (pl.col("purchase_timestamp") < window_end)
    )
    return TemporalSplit(train=train, test=test, cutoff=cutoff, window_end=window_end)


NUMERIC_FEATURES = [
    "distance_km",
    "estimated_slack_days",
    "item_count",
    "total_freight",
    "total_price",
    "total_weight_g",
    "total_volume_cm3",
    "purchase_day_of_week",
    "purchase_hour",
]

NULLABLE_FEATURES = ["distance_km", "total_weight_g", "total_volume_cm3"]


def prepare_matrix(train: pl.DataFrame, test: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Impute missing values and flag where they were missing.

    Medians come from the training set and are applied to both. Computing them
    over the combined data would leak information about the test period into
    the model.

    A missing distance is not a median distance, so the imputed value is
    accompanied by an indicator. The model can then treat "unknown" as its own
    condition rather than as an average order.
    """
    medians = {column: train[column].median() for column in NULLABLE_FEATURES}

    def transform(frame: pl.DataFrame) -> pl.DataFrame:
        return frame.with_columns(
            [
                pl.col(column).is_null().cast(pl.Float64).alias(f"{column}_missing")
                for column in NULLABLE_FEATURES
            ]
            + [pl.col(column).fill_null(medians[column]) for column in NULLABLE_FEATURES]
        ).select(NUMERIC_FEATURES + [f"{c}_missing" for c in NULLABLE_FEATURES])

    return transform(train), transform(test)


class Evaluation(NamedTuple):
    """How a set of predictions did on a test window."""

    brier: float
    auc: float | None
    mean_predicted: float
    observed_rate: float


def evaluate(predicted: np.ndarray, actual: np.ndarray) -> Evaluation:
    """Score predictions on discrimination and calibration separately.

    Brier score measures calibration — whether the probabilities are right.
    AUC measures discrimination — whether riskier orders are ranked above
    safer ones. A model can rank well and be badly calibrated, which is the
    expected outcome here: the late rate moves far more between months than
    any feature explains.

    AUC is undefined when every outcome in the window is the same, which is
    why it may be None.
    """
    both_classes = len(set(actual)) > 1
    return Evaluation(
        brier=float(brier_score_loss(actual, predicted)),
        auc=float(roc_auc_score(actual, predicted)) if both_classes else None,
        mean_predicted=float(predicted.mean()),
        observed_rate=float(actual.mean()),
    )


def fit_logistic(features: pl.DataFrame, target: np.ndarray) -> Pipeline:
    """Fit a logistic regression on the prepared feature matrix.

    Scaling is part of the pipeline rather than a separate step, so the
    scaler is fitted on training data only and travels with the model. A
    scaler fitted separately is one more thing that can be forgotten at
    prediction time.

    Classes are not balanced. Weighting the minority class upward improves
    recall at a fixed threshold, but it does so by inflating every predicted
    probability, and the probabilities are the output that matters here. If a
    binary decision is needed, the threshold is chosen afterwards.
    """
    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000)),
        ]
    )
    pipeline.fit(features.to_numpy(), target)
    return pipeline
