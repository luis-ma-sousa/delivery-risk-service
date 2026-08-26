"""The HTTP service.

The endpoint depends on the RiskModel protocol, never on a concrete model.
Swapping the constant model for a trained one changes nothing in this file.
"""

from fastapi import FastAPI

from delivery_risk.api.schemas import PredictionRequest, PredictionResponse
from delivery_risk.prediction import ConstantModel, RiskModel

app = FastAPI(
    title="Delivery Risk Service",
    description=(
        "Predicts the probability that an order is delivered after its " "estimated delivery date."
    ),
    version="0.1.0",
)

model: RiskModel = ConstantModel()


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the service is up and which model is loaded."""
    return {"status": "ok", "model_version": model.version}


@app.post("/predict")
def predict(request: PredictionRequest) -> PredictionResponse:
    """Return the probability that this order is delivered late.

    The feature layer does not exist yet, so nothing is read from the database
    and the request is not yet used. The contract is what matters here: it is
    settled before the intelligence behind it is.
    """
    probability = model.predict_probability({})
    return PredictionResponse(
        probability_late=probability,
        model_version=model.version,
    )
