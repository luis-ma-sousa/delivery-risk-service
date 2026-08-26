"""The prediction interface and its implementations.

The API depends on the Protocol, never on a concrete model. Anything that
satisfies the interface can be substituted without the HTTP layer knowing:
that separation is what lets the skeleton be built and tested before any model
exists.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class RiskModel(Protocol):
    """Anything that can turn a set of features into a probability."""

    @property
    def version(self) -> str:
        """An identifier returned with every prediction it produces."""
        ...

    def predict_probability(self, features: dict[str, float | None]) -> float:
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

    def predict_probability(self, features: dict[str, float | None]) -> float:
        return self._probability
