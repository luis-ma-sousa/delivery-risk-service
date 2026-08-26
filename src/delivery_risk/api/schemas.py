"""HTTP request and response contracts.

These describe what a caller sends and receives. They are deliberately not the
ORM models: the request carries what a checkout system knows at order creation
(ADR 0015), which is a smaller and differently shaped thing than a row in
`curated`.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

PaymentType = Literal["credit_card", "boleto", "voucher", "debit_card"]


class OrderLine(BaseModel):
    """One item of an order, as the caller knows it at checkout."""

    product_id: str = Field(min_length=1)
    seller_id: str = Field(min_length=1)
    price: Decimal = Field(ge=0)
    freight_value: Decimal = Field(ge=0)


class PredictionRequest(BaseModel):
    """An order at the moment it is placed.

    Everything here is available at the prediction point (ADR 0014). Product
    attributes and coordinates are absent by design: the service resolves those
    from the catalogue rather than trusting the caller for them.
    """

    purchase_timestamp: datetime
    estimated_delivery_date: datetime
    customer_zip_code_prefix: str = Field(min_length=1, max_length=8)
    payment_type: PaymentType
    payment_installments: int = Field(ge=0)
    payment_value: Decimal = Field(ge=0)
    items: list[OrderLine] = Field(min_length=1)


class PredictionResponse(BaseModel):
    """The probability that the order is delivered after its estimated date."""

    probability_late: float = Field(ge=0.0, le=1.0)
    model_version: str
