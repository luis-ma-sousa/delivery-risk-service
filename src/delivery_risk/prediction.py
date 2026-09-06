"""The prediction interface and its implementations.

The API depends on the Protocol, never on a concrete model. Anything that
satisfies the interface can be substituted without the HTTP layer knowing:
that separation is what lets the skeleton be built and tested before any model
exists.
"""

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

import joblib
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
    """A model loaded from a directory on disk.

    The column order and imputation medians are read from the metadata file
    rather than assumed. Scikit-learn matches features by position, so a
    mismatch between what the service computes and what the model expects
    would be silent: the model would receive distance where it expects weight
    and would answer confidently.
    """

    def __init__(self, directory: Path) -> None:
        metadata = json.loads((directory / "model.json").read_text())
        self._model = joblib.load(directory / "model.joblib")
        self._columns: list[str] = metadata["columns"]
        self._medians: dict[str, float] = metadata["medians"]
        self._trained_through: str = metadata["trained_through"]

    @property
    def version(self) -> str:
        return f"logistic-{self._trained_through}"

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
            elif isinstance(value, str):
                row.append(0.0)
            else:
                row.append(float(value))

        probability = self._model.predict_proba(np.array([row]))[0][1]
        return float(probability)
