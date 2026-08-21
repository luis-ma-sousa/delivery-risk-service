"""Faithful mirror of the source CSVs.

Every column is text and no domain constraint is declared, per ADR 0009 and
ADR 0001. This layer must accept any row the source provides; rejection is the
job of the transformation into `curated`.
"""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from delivery_risk.models.base import Base
from sqlalchemy import BigInteger, Text

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


class RawCustomer(Base):
    __tablename__ = "customers"
    __table_args__ = {"schema": "raw"}

    customer_id: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_unique_id: Mapped[str] = mapped_column(Text)
    customer_zip_code_prefix: Mapped[str] = mapped_column(Text)
    customer_city: Mapped[str] = mapped_column(Text)
    customer_state: Mapped[str] = mapped_column(Text)

class RawOrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = {"schema": "raw"}

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[str] = mapped_column(Text)
    seller_id: Mapped[str] = mapped_column(Text)
    shipping_limit_date: Mapped[str] = mapped_column(Text)
    price: Mapped[str] = mapped_column(Text)
    freight_value: Mapped[str] = mapped_column(Text)


class RawOrderPayment(Base):
    __tablename__ = "order_payments"
    __table_args__ = {"schema": "raw"}

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    payment_sequential: Mapped[str] = mapped_column(Text, primary_key=True)
    payment_type: Mapped[str] = mapped_column(Text)
    payment_installments: Mapped[str] = mapped_column(Text)
    payment_value: Mapped[str] = mapped_column(Text)


class RawProduct(Base):
    __tablename__ = "products"
    __table_args__ = {"schema": "raw"}

    product_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_category_name: Mapped[str | None] = mapped_column(Text)
    product_name_lenght: Mapped[str | None] = mapped_column(Text)
    product_description_lenght: Mapped[str | None] = mapped_column(Text)
    product_photos_qty: Mapped[str | None] = mapped_column(Text)
    product_weight_g: Mapped[str | None] = mapped_column(Text)
    product_length_cm: Mapped[str | None] = mapped_column(Text)
    product_height_cm: Mapped[str | None] = mapped_column(Text)
    product_width_cm: Mapped[str | None] = mapped_column(Text)


class RawSeller(Base):
    __tablename__ = "sellers"
    __table_args__ = {"schema": "raw"}

    seller_id: Mapped[str] = mapped_column(Text, primary_key=True)
    seller_zip_code_prefix: Mapped[str] = mapped_column(Text)
    seller_city: Mapped[str] = mapped_column(Text)
    seller_state: Mapped[str] = mapped_column(Text)


class RawGeolocation(Base):
    __tablename__ = "geolocation"
    __table_args__ = {"schema": "raw"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    geolocation_zip_code_prefix: Mapped[str] = mapped_column(Text)
    geolocation_lat: Mapped[str] = mapped_column(Text)
    geolocation_lng: Mapped[str] = mapped_column(Text)
    geolocation_city: Mapped[str] = mapped_column(Text)
    geolocation_state: Mapped[str] = mapped_column(Text)


class RawCategoryTranslation(Base):
    __tablename__ = "category_translation"
    __table_args__ = {"schema": "raw"}

    product_category_name: Mapped[str] = mapped_column(Text, primary_key=True)
    product_category_name_english: Mapped[str] = mapped_column(Text)

class RawOrderReview(Base):
    __tablename__ = "order_reviews"
    __table_args__ = {"schema": "raw"}

    review_id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    review_score: Mapped[str] = mapped_column(Text)
    review_comment_title: Mapped[str | None] = mapped_column(Text)
    review_comment_message: Mapped[str | None] = mapped_column(Text)
    review_creation_date: Mapped[str] = mapped_column(Text)
    review_answer_timestamp: Mapped[str] = mapped_column(Text)