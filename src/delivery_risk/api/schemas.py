"""HTTP request and response contracts.

These describe what a caller sends and receives. They are deliberately not the
ORM models: the request carries what a checkout system knows at order creation
(ADR 0015), which is a smaller and differently shaped thing than a row in
`curated`.
"""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

PaymentType = Literal["credit_card", "boleto", "voucher", "debit_card"]


class OrderLine(BaseModel):
    """One item of an order, as the caller knows it at checkout."""

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1)
    seller_id: str = Field(min_length=1)
    price: Decimal = Field(ge=0)
    freight_value: Decimal = Field(ge=0)


class PredictionRequest(BaseModel):
    """An order at the moment it is placed.

    Everything here is available at the prediction point (ADR 0014). Product
    attributes and coordinates are absent by design: the service resolves those
    from the catalogue rather than trusting the caller for them.

    Unknown fields are rejected rather than ignored. A caller that sends an
    outcome column has misunderstood the contract, and silently discarding it
    would leave them believing it was used.

    Timestamps must carry an offset. The service does not guess a timezone for
    a caller that omits one: unlike the CSV ingestion, where the source cannot
    be asked, a caller knows its own timezone and can say so.
    """

    model_config = ConfigDict(extra="forbid")

    purchase_timestamp: AwareDatetime
    estimated_delivery_date: AwareDatetime
    customer_zip_code_prefix: str = Field(min_length=1, max_length=8)
    payment_type: PaymentType
    payment_installments: int = Field(ge=0)
    payment_value: Decimal = Field(ge=0)
    items: list[OrderLine] = Field(min_length=1)

    @model_validator(mode="after")
    def estimate_must_follow_purchase(self) -> "PredictionRequest":
        """Reject an estimate that precedes the purchase it belongs to."""
        if self.estimated_delivery_date < self.purchase_timestamp:
            raise ValueError("estimated_delivery_date must not precede purchase_timestamp")
        return self


class PredictionResponse(BaseModel):
    """The probability that the order is delivered after its estimated date."""

    probability_late: float = Field(ge=0.0, le=1.0)
    model_version: str
