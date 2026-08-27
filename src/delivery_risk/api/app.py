"""The HTTP service.

The endpoint depends on the RiskModel protocol, never on a concrete model.
Swapping the constant model for a trained one changes nothing in this file.
"""

from collections.abc import Generator

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from delivery_risk.api.schemas import PredictionRequest, PredictionResponse
from delivery_risk.database import get_session
from delivery_risk.features import build_features
from delivery_risk.prediction import ConstantModel, RiskModel

app = FastAPI(
    title="Delivery Risk Service",
    description=(
        "Predicts the probability that an order is delivered after its estimated delivery date."
    ),
    version="0.1.0",
)

model: RiskModel = ConstantModel()


def session_dependency() -> Generator[Session, None, None]:
    """Provide a database session for the duration of one request."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the service is up and which model is loaded."""
    return {"status": "ok", "model_version": model.version}


@app.post("/predict")
def predict(
    request: PredictionRequest,
    session: Session = Depends(session_dependency),
) -> PredictionResponse:
    """Return the probability that this order is delivered late.

    Product attributes and coordinates are resolved from `curated` rather than
    taken from the caller (ADR 0015), so this endpoint reads the database on
    every request.
    """
    features = build_features(session, request)
    probability = model.predict_probability(features)
    return PredictionResponse(
        probability_late=probability,
        model_version=model.version,
    )
