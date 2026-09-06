"""The prediction interface and its implementations.

The API depends on the Protocol, never on a concrete model. Anything that
satisfies the interface can be substituted without the HTTP layer knowing:
that separation is what lets the skeleton be built and tested before any model
exists.
"""

from typing import Protocol, runtime_checkable

import mlflow
import mlflow.sklearn
import numpy as np


@runtime_checkable
class RiskModel(Protocol):
    """Anything that can turn a set of features into a probability."""

    @property
    def version(self) -> str:
        """An identifier returned with every prediction it produces."""
        ...

    def predict_probability(self, features: dict[str, float | str | None]) -> float:
        """Return the probability that the order is delivered late."""
        ...


class ConstantModel:
    """A model that always answers 0.5.

    It exists so the service can be built, tested and deployed before any real
    model does. A constant of 0.5 is deliberate: it asserts nothing, so any
    downstream code that appears to work with it is not relying on the answer.
    """

    def __init__(self, probability: float = 0.5) -> None:
        self._probability = probability

    @property
    def version(self) -> str:
        return "constant-0.1.0"

    def predict_probability(self, features: dict[str, float | str | None]) -> float:
        return self._probability


class TrainedModel:
    """A model loaded from an MLflow run.

    The column order and imputation medians are read from the run rather than
    assumed. Scikit-learn matches features by position, so a mismatch between
    what the service computes and what the model expects would be silent: the
    model would receive distance where it expects weight and would answer
    confidently.
    """

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._model = mlflow.sklearn.load_model(f"runs:/{run_id}/model")
        metadata = mlflow.artifacts.load_dict(f"runs:/{run_id}/feature_columns.json")
        self._columns: list[str] = metadata["columns"]
        self._medians: dict[str, float] = metadata["medians"]

    @property
    def version(self) -> str:
        return f"logistic-{self._run_id[:8]}"

    def predict_probability(self, features: dict[str, float | str | None]) -> float:
        row: list[float] = []
        for column in self._columns:
            if column.endswith("_missing"):
                source = column.removesuffix("_missing")
                row.append(1.0 if features.get(source) is None else 0.0)
                continue

            value = features.get(column)
            if value is None:
                row.append(self._medians[column])
            else:
                row.append(float(value))

        probability = self._model.predict_proba(np.array([row]))[0][1]
        return float(probability)
