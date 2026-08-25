"""The domain model: typed, constrained, and analysis-ready.

Every constraint here is traceable to a measurement in the reconnaissance
output. Rows that would violate one are excluded during transformation rather
than accommodated, per ADR 0001. Column names drop the redundant table prefix
per ADR 0011.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from delivery_risk.models.base import Base

ORDER_STATUSES = (
    "delivered",
    "shipped",
    "canceled",
    "unavailable",
    "invoiced",
    "processing",
    "created",
    "approved",
)


class Person(Base):
    """A recurring buyer, identified across orders.

    Separated from the per-order customer record per ADR 0005: the source
    customer table holds one row per order, not one per person. 96096 rows,
    of which 2997 placed more than one order.
    """

    __tablename__ = "persons"
    __table_args__ = {"schema": "curated"}

    person_id: Mapped[str] = mapped_column(Text, primary_key=True)


class ZipCodeLocation(Base):
    """One representative coordinate per postcode prefix.

    Collapsed from the million geocoded points in `raw.geolocation` by median,
    per ADR 0003. Points outside the Brazil bounding box are discarded before
    aggregation. The prefix is text, never an integer: prefixes in the
    01000-09999 range carry a leading zero that integer parsing discards.
    """

    __tablename__ = "zip_code_locations"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -34.0 AND 5.3", name="zip_latitude_in_brazil"),
        CheckConstraint(
            "longitude BETWEEN -74.0 AND -34.8", name="zip_longitude_in_brazil"
        ),
        {"schema": "curated"},
    )

    zip_code_prefix: Mapped[str] = mapped_column(Text, primary_key=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)


class CategoryTranslation(Base):
    """Portuguese to English mapping for product categories."""

    __tablename__ = "category_translation"
    __table_args__ = {"schema": "curated"}

    category_name: Mapped[str] = mapped_column(Text, primary_key=True)
    category_name_english: Mapped[str] = mapped_column(Text, nullable=False)


class Customer(Base):
    """The delivery address attached to a single order.

    One row per order, not per person: the relationship to `orders` is 1:1,
    confirmed by zero orphans in both directions. The name is inherited from
    the source and is misleading; see ADR 0005.

    The postcode foreign key is nullable and 278 rows will not resolve: those
    prefixes are absent from the geolocation catalogue (ADR 0004).
    """

    __tablename__ = "customers"
    __table_args__ = {"schema": "curated"}

    customer_id: Mapped[str] = mapped_column(Text, primary_key=True)
    person_id: Mapped[str] = mapped_column(
        ForeignKey("curated.persons.person_id"), nullable=False
    )
    zip_code_prefix: Mapped[str | None] = mapped_column(
        ForeignKey("curated.zip_code_locations.zip_code_prefix")
    )
    city: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)


class Seller(Base):
    """A seller and the postcode they despatch from.

    Seven of 3095 sellers have a prefix absent from the geolocation catalogue,
    so the foreign key is nullable for the same reason as on customers.
    """

    __tablename__ = "sellers"
    __table_args__ = {"schema": "curated"}

    seller_id: Mapped[str] = mapped_column(Text, primary_key=True)
    zip_code_prefix: Mapped[str | None] = mapped_column(
        ForeignKey("curated.zip_code_locations.zip_code_prefix")
    )
    city: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)


class Product(Base):
    """A product and its physical dimensions.

    610 products carry no descriptive metadata at all — category, name length,
    description length and photo count are null together. Two products have no
    physical dimensions. Both groups are kept: absent metadata may itself be
    informative.

    `length` corrects the source spelling `lenght` (ADR 0011).
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("weight_g IS NULL OR weight_g >= 0", name="products_weight_non_negative"),
        {"schema": "curated"},
    )

    product_id: Mapped[str] = mapped_column(Text, primary_key=True)
    category_name: Mapped[str | None] = mapped_column(
        ForeignKey("curated.category_translation.category_name")
    )
    name_length: Mapped[int | None] = mapped_column(Integer)
    description_length: Mapped[int | None] = mapped_column(Integer)
    photos_qty: Mapped[int | None] = mapped_column(Integer)
    weight_g: Mapped[int | None] = mapped_column(Integer)
    length_cm: Mapped[int | None] = mapped_column(Integer)
    height_cm: Mapped[int | None] = mapped_column(Integer)
    width_cm: Mapped[int | None] = mapped_column(Integer)


class Order(Base):
    """An order, from purchase to delivery.

    Timestamps are stored with timezone in America/Sao_Paulo per ADR 0002.

    No constraint relates the estimated delivery date to the actual one: an
    order delivered after its estimate is the target variable, not a violation.
    No constraint relates approval to carrier handover either — 1359 orders
    reverse that order because the two timestamps come from independent
    systems (ADR 0006).
    """

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(f"status IN {ORDER_STATUSES}", name="orders_status_valid"),
        CheckConstraint(
            "approved_at IS NULL OR approved_at >= purchase_timestamp",
            name="orders_approved_after_purchase",
        ),
        CheckConstraint(
            "delivered_customer_date IS NULL "
            "OR delivered_carrier_date IS NULL "
            "OR delivered_customer_date >= delivered_carrier_date",
            name="orders_delivered_after_despatch",
        ),
        {"schema": "curated"},
    )

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("curated.customers.customer_id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    purchase_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    delivered_carrier_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    delivered_customer_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    estimated_delivery_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )


class OrderItem(Base):
    """One line of an order: a product from a seller.

    The primary key is composite. `order_item_id` counts items within an
    order — it runs from 1 to 21 and is not a global identifier, despite the
    name inherited from the source.
    """

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("price >= 0", name="order_items_price_non_negative"),
        CheckConstraint("freight_value >= 0", name="order_items_freight_non_negative"),
        {"schema": "curated"},
    )

    order_id: Mapped[str] = mapped_column(
        ForeignKey("curated.orders.order_id"), primary_key=True
    )
    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("curated.products.product_id"), nullable=False
    )
    seller_id: Mapped[str] = mapped_column(
        ForeignKey("curated.sellers.seller_id"), nullable=False
    )
    shipping_limit_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    freight_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


class OrderPayment(Base):
    """One payment against an order.

    An order may have several payments, and one delivered order has none at
    all: the relationship is 0:N, not 1:N, so nothing here requires a payment
    to exist.
    """

    __tablename__ = "order_payments"
    __table_args__ = (
        CheckConstraint("value >= 0", name="order_payments_value_non_negative"),
        CheckConstraint("installments >= 0", name="order_payments_installments_non_negative"),
        {"schema": "curated"},
    )

    order_id: Mapped[str] = mapped_column(
        ForeignKey("curated.orders.order_id"), primary_key=True
    )
    payment_sequential: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_type: Mapped[str] = mapped_column(Text, nullable=False)
    installments: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)