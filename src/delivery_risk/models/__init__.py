"""ORM models for every layer of the database.

Importing the layer modules here guarantees that their classes are registered
on `Base.metadata` before Alembic inspects it. A model that is never imported
is a table Alembic cannot see, and autogenerate would propose dropping it.
"""

from delivery_risk.models.base import Base
from delivery_risk.models.raw import (
    RawCategoryTranslation,
    RawCustomer,
    RawGeolocation,
    RawOrder,
    RawOrderItem,
    RawOrderPayment,
    RawOrderReview,
    RawProduct,
    RawSeller,
)
from delivery_risk.models.curated import (
    CategoryTranslation,
    Customer,
    Order,
    OrderItem,
    OrderPayment,
    Person,
    Product,
    Seller,
    ZipCodeLocation,
)


__all__ = [
    "Base",
    "CategoryTranslation",
    "Customer",
    "Order",
    "OrderItem",
    "OrderPayment",
    "Person",
    "Product",
    "RawCategoryTranslation",
    "RawCustomer",
    "RawGeolocation",
    "RawOrder",
    "RawOrderItem",
    "RawOrderPayment",
    "RawOrderReview",
    "RawProduct",
    "RawSeller",
    "Seller",
    "ZipCodeLocation",
]