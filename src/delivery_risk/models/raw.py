"""Faithful mirror of the source CSVs.

Every column is text and no domain constraint is declared, per ADR 0009 and
ADR 0001. This layer must accept any row the source provides; rejection is the
job of the transformation into `curated`.
"""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from delivery_risk.models.base import Base


class RawOrder(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "raw"}

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text)
    order_status: Mapped[str] = mapped_column(Text)
    order_purchase_timestamp: Mapped[str] = mapped_column(Text)
    order_approved_at: Mapped[str | None] = mapped_column(Text)
    order_delivered_carrier_date: Mapped[str | None] = mapped_column(Text)
    order_delivered_customer_date: Mapped[str | None] = mapped_column(Text)
    order_estimated_delivery_date: Mapped[str] = mapped_column(Text)