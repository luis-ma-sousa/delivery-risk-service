"""Training data preparation and evaluation.

Splits are temporal, never random. The late-delivery rate ranges from 1.4% to
21.4% across months of this dataset, so a random split would let the model see
orders from the same week it is being evaluated on, and learn a rate it could
not know in advance (ADR 0019).
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import NamedTuple, Protocol, cast
from zoneinfo import ZoneInfo

import mlflow
import mlflow.sklearn
import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SAO_PAULO = ZoneInfo("America/Sao_Paulo")

USABLE_FROM = datetime(2017, 1, 1, tzinfo=SAO_PAULO)
USABLE_UNTIL = datetime(2018, 9, 1, tzinfo=SAO_PAULO)

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

REFERENCE_LAG_DAYS = 30
REFERENCE_WINDOW_DAYS = 30

FEATURE_COLUMNS = NUMERIC_FEATURES + [f"{c}_missing" for c in NULLABLE_FEATURES]


class TemporalSplit(NamedTuple):
    """Orders before a cutoff, and orders in the window after it."""

    train: pl.DataFrame
    test: pl.DataFrame
    cutoff: datetime
    window_end: datetime


class Evaluation(NamedTuple):
    """How a set of predictions did on a test window."""

    brier: float
    auc: float | None
    mean_predicted: float
    observed_rate: float


class ExperimentResult(NamedTuple):
    """A model's performance on a window, and what a constant would have scored."""

    model: Evaluation
    baseline: Evaluation
    train_orders: int
    test_orders: int


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


class ProbabilityModel(Protocol):
    """Anything that can be fitted and asked for class probabilities.

    Both the logistic pipeline and the gradient boosting classifier satisfy
    this without inheriting from it: scikit-learn's estimators share the
    interface by convention, and the Protocol makes that convention checkable.
    """

    def predict_proba(self, x: np.ndarray) -> np.ndarray: ...


ModelFitter = Callable[[pl.DataFrame, np.ndarray], ProbabilityModel]


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


def prepare_matrix(train: pl.DataFrame, test: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Impute missing values and flag where they were missing.

    Medians come from the training set and are applied to both. Computing them
    over the combined data would leak information about the test period into
    the model.

    A missing distance is not a median distance, so the imputed value is
    accompanied by an indicator. The model can then treat "unknown" as its own
    condition rather than as an average order (ADR 0020).
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


def reference_rate(features: pl.DataFrame, cutoff: datetime) -> float:
    """The observed late rate over a window whose outcomes would be known.

    Recalibrating on the weeks immediately before the cutoff would assume
    knowledge nobody has: those orders are still in transit. Delivery takes a
    median of 10 days and 23 at the ninetieth percentile, so a thirty-day lag
    leaves roughly 95% of outcomes settled.

    The 5% still open are the slowest, so this rate is slightly optimistic.
    """
    window_end = cutoff - timedelta(days=REFERENCE_LAG_DAYS)
    window_start = window_end - timedelta(days=REFERENCE_WINDOW_DAYS)

    window = features.filter(
        (pl.col("purchase_timestamp") >= window_start) & (pl.col("purchase_timestamp") < window_end)
    )
    return float(cast(float, window["is_late"].mean()))


def recalibrate(predicted: np.ndarray, target_rate: float) -> np.ndarray:
    """Shift predictions so their mean matches a target rate.

    The shift is a constant added in log-odds space, which moves every
    probability in the same direction without changing their order. The model
    ranks orders well and is wrong about the level; this corrects the level
    and leaves the ranking untouched.
    """
    if target_rate <= 0 or target_rate >= 1:
        return predicted

    log_odds = np.log(predicted / (1 - predicted))
    current = float(predicted.mean())
    shift = np.log(target_rate / (1 - target_rate)) - np.log(current / (1 - current))

    calibrated: np.ndarray = 1 / (1 + np.exp(-(log_odds + shift)))
    return calibrated


def fit_gradient_boosting(
    features: pl.DataFrame, target: np.ndarray
) -> HistGradientBoostingClassifier:
    """Fit a histogram-based gradient boosting classifier.

    No scaling: tree splits are invariant to monotonic transformations of a
    feature, so standardising would change nothing.

    The same imputed matrix as the logistic regression is used, even though
    this model handles missing values natively. Changing the model and the
    preprocessing at once would leave it unclear which produced the
    difference.
    """
    model = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        max_depth=None,
        random_state=0,
    )
    model.fit(features.to_numpy(), target)
    return model


def train_and_register(features: pl.DataFrame) -> str:
    """Train on all usable data and register the model in MLflow.

    The column order and the imputation medians are logged with the model.
    Scikit-learn matches features by position, so a model that outlives the
    code that built it needs to carry the order it expects, or the service
    will feed it distance where it expects weight. The medians travel for the
    same reason: an order whose distance cannot be resolved must be filled the
    same way at prediction time as it was during training (ADR 0020).
    """
    matrix, _ = prepare_matrix(features, features)
    target = features["is_late"].to_numpy()
    model = fit_logistic(matrix, target)

    medians = {
        column: float(cast(float, features[column].median())) for column in NULLABLE_FEATURES
    }

    with mlflow.start_run(run_name="production-candidate") as run:
        mlflow.log_params(
            {
                "model": "logistic_regression",
                "train_orders": features.height,
                "trained_through": cast(datetime, features["purchase_timestamp"].max())
                .date()
                .isoformat(),
            }
        )
        mlflow.log_metric("train_rate", float(target.mean()))
        mlflow.log_dict({"columns": FEATURE_COLUMNS, "medians": medians}, "feature_columns.json")
        mlflow.sklearn.log_model(model, name="model")
        return str(run.info.run_id)


def run_experiment(
    features: pl.DataFrame,
    cutoff: datetime,
    window_end: datetime,
    fit: ModelFitter = fit_logistic,
    model_name: str = "logistic_regression",
) -> ExperimentResult:
    """Train on everything before the cutoff and score the window after it.

    The fitting function is a parameter rather than a branch: adding a model
    means writing a function, not editing this one.
    """
    split = split_at(features, cutoff, window_end)
    x_train, x_test = prepare_matrix(split.train, split.test)
    y_train = split.train["is_late"].to_numpy()
    y_test = split.test["is_late"].to_numpy()

    model = fit(x_train, y_train)
    predicted = model.predict_proba(x_test.to_numpy())[:, 1]

    result = evaluate(predicted, y_test)
    baseline = evaluate(np.full(len(y_test), y_train.mean()), y_test)

    with mlflow.start_run(run_name=f"{cutoff.strftime('%Y-%m')}-{model_name}"):
        mlflow.log_params(
            {
                "cutoff": cutoff.date().isoformat(),
                "window_end": window_end.date().isoformat(),
                "model": model_name,
                "train_orders": split.train.height,
                "test_orders": split.test.height,
            }
        )
        mlflow.log_metrics(
            {
                "brier": result.brier,
                "auc": result.auc if result.auc is not None else float("nan"),
                "mean_predicted": result.mean_predicted,
                "observed_rate": result.observed_rate,
                "baseline_brier": baseline.brier,
                "train_rate": float(y_train.mean()),
            }
        )

    return ExperimentResult(
        model=result,
        baseline=baseline,
        train_orders=split.train.height,
        test_orders=split.test.height,
    )
