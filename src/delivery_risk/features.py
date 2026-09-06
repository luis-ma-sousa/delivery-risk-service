from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import NamedTuple
from zoneinfo import ZoneInfo

import polars as pl
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from delivery_risk.api.schemas import PredictionRequest

EARTH_RADIUS_KM = 6371.0
SECONDS_PER_DAY = 86400.0
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class UnknownSellerError(Exception):
    """Raised when a request names a seller the catalogue does not contain.

    Distinct from a seller whose postcode has no coordinates, which is
    expected and yields a null distance (ADR 0015).
    """

    def __init__(self, seller_ids: list[str]) -> None:
        self.seller_ids = seller_ids
        super().__init__(f"unknown sellers: {', '.join(seller_ids)}")


class UnknownProductError(Exception):
    """Raised when a request names a product the catalogue does not contain."""

    def __init__(self, product_ids: list[str]) -> None:
        self.product_ids = product_ids
        super().__init__(f"unknown products: {', '.join(product_ids)}")


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in kilometres.

    This is straight-line distance over the surface of a sphere, not distance
    by road. Brazilian road distance exceeds it by a wide and uneven margin:
    the network is dense along the coast and sparse inland, so two journeys of
    equal great-circle length can differ greatly by road. Origin and
    destination state are carried as separate features precisely so the model
    can learn that difference, rather than paying for a routing API that could
    not be queried retroactively for the training period anyway.
    """
    lat1, lng1, lat2, lng2 = (radians(v) for v in (lat1, lng1, lat2, lng2))

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def customer_location(session: Session, zip_code_prefix: str) -> tuple[float, float] | None:
    """Return the coordinates of a postcode prefix, or None if it is unknown.

    278 customers in the training data carry a prefix the catalogue does not
    cover (ADR 0004). A missing location is not an error; it means the distance
    cannot be computed for this order.
    """
    row = session.execute(
        text(
            """
            SELECT latitude, longitude
            FROM curated.zip_code_locations
            WHERE zip_code_prefix = :prefix
            """
        ),
        {"prefix": zip_code_prefix},
    ).first()

    if row is None:
        return None
    return float(row.latitude), float(row.longitude)


def seller_locations(
    session: Session, seller_ids: list[str]
) -> dict[str, tuple[float, float] | None]:
    """Return the coordinates of each known seller, keyed by identifier.

    The three possible outcomes are distinct and the caller needs to tell them
    apart (ADR 0015):

    - the key is absent: no such seller, which is a bad request
    - the key maps to None: the seller exists but its postcode prefix is not
      in the catalogue, which is expected for seven of them (ADR 0004)
    - the key maps to coordinates: resolved
    """

    rows = session.execute(
        text(
            """
            SELECT s.seller_id, z.latitude, z.longitude
            FROM curated.sellers s
            LEFT JOIN curated.zip_code_locations z
                   ON z.zip_code_prefix = s.zip_code_prefix
            WHERE s.seller_id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": list(seller_ids)},
    ).all()

    return {
        row.seller_id: (
            None if row.latitude is None else (float(row.latitude), float(row.longitude))
        )
        for row in rows
    }


class ProductAttributes(NamedTuple):
    """The physical and descriptive attributes of a product.

    Every field is optional: 610 products carry no descriptive metadata at all
    and two have no dimensions. Their absence is preserved rather than filled,
    since it may itself be informative.
    """

    weight_g: int | None
    length_cm: int | None
    height_cm: int | None
    width_cm: int | None
    category_name: str | None


def product_attributes(session: Session, product_ids: list[str]) -> dict[str, ProductAttributes]:
    """Return the attributes of each known product, keyed by identifier.

    A product absent from the catalogue is absent from the result. As with
    sellers, that is a bad request rather than a missing value (ADR 0015).
    """
    rows = session.execute(
        text(
            """
            SELECT product_id, weight_g, length_cm, height_cm, width_cm,
                   category_name
            FROM curated.products
            WHERE product_id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": list(product_ids)},
    ).all()

    return {
        row.product_id: ProductAttributes(
            weight_g=row.weight_g,
            length_cm=row.length_cm,
            height_cm=row.height_cm,
            width_cm=row.width_cm,
            category_name=row.category_name,
        )
        for row in rows
    }


def distance_km(
    customer: tuple[float, float] | None,
    sellers: list[tuple[float, float] | None],
) -> float | None:
    """Distance from the customer to the furthest seller, in kilometres.

    The furthest rather than the average: an order is complete when its last
    item arrives, so the bottleneck is the item travelling furthest. 98.7% of
    orders have a single seller, so the choice rarely matters.

    Returns None when any coordinate is missing. A maximum computed over the
    sellers we happen to know would not be the furthest, which is what this
    feature claims to be.
    """
    if customer is None or not sellers:
        return None
    if any(seller is None for seller in sellers):
        return None

    return max(
        haversine_km(customer[0], customer[1], seller[0], seller[1])
        for seller in sellers
        if seller is not None
    )


def estimated_slack_days(purchase: datetime, estimate: datetime) -> float:
    """Days between the purchase and the delivery estimate.

    Fractional rather than whole days: the estimate always falls at midnight,
    so the fraction carries the hour of purchase, and whether that matters is
    for the model to decide.
    """
    return (estimate - purchase).total_seconds() / SECONDS_PER_DAY


def total_weight_g(products: list[ProductAttributes]) -> float | None:
    """Combined weight of every item, in grams.

    None when any product has no recorded weight: a sum over the products that
    happen to have one is not the weight of the order.
    """
    if not products:
        return None
    if any(product.weight_g is None for product in products):
        return None

    return float(sum(product.weight_g or 0 for product in products))


def total_volume_cm3(products: list[ProductAttributes]) -> float | None:
    """Combined volume of every item, in cubic centimetres.

    Bounding-box volume, not the volume of the object: a mug and the box it
    ships in occupy the same space in a van, and it is the van that matters.
    """
    if not products:
        return None
    if any(
        product.length_cm is None or product.height_cm is None or product.width_cm is None
        for product in products
    ):
        return None

    return float(
        sum(
            (product.length_cm or 0) * (product.height_cm or 0) * (product.width_cm or 0)
            for product in products
        )
    )


def seller_states(session: Session, seller_ids: list[str]) -> dict[str, str]:
    """Return the state each seller despatches from, keyed by identifier."""
    rows = session.execute(
        text(
            """
            SELECT seller_id, state
            FROM curated.sellers
            WHERE seller_id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": list(seller_ids)},
    ).all()

    return {row.seller_id: row.state for row in rows}


def origin_state(states: dict[str, str], seller_ids: list[str]) -> str | None:
    """The state the order despatches from.

    None when the order has sellers in more than one state: there is no single
    origin, and picking one would assert something the data does not say. This
    affects 1.3% of orders.
    """
    distinct = {states[seller_id] for seller_id in seller_ids if seller_id in states}
    if len(distinct) != 1:
        return None
    return distinct.pop()


def build_features(session: Session, request: PredictionRequest) -> dict[str, float | str | None]:
    """Turn a request into the features the model expects.

    Day of week and hour are taken in America/Sao_Paulo, not in whatever
    offset the caller sent (ADR 0018). Sellers and products the catalogue does
    not contain are the caller's error and are raised rather than skipped
    (ADR 0015).
    """
    prefix = request.customer_zip_code_prefix
    seller_ids = [item.seller_id for item in request.items]
    product_ids = [item.product_id for item in request.items]

    customer = customer_location(session, prefix)
    sellers = seller_locations(session, seller_ids)
    products = product_attributes(session, product_ids)
    states = seller_states(session, seller_ids)

    unknown_sellers = [seller_id for seller_id in seller_ids if seller_id not in sellers]
    if unknown_sellers:
        raise UnknownSellerError(unknown_sellers)

    unknown_products = [product_id for product_id in product_ids if product_id not in products]
    if unknown_products:
        raise UnknownProductError(unknown_products)

    resolved_products = [products[product_id] for product_id in product_ids]
    local_purchase = request.purchase_timestamp.astimezone(SAO_PAULO)

    return {
        "distance_km": distance_km(customer, list(sellers.values())),
        "estimated_slack_days": estimated_slack_days(
            request.purchase_timestamp, request.estimated_delivery_date
        ),
        "item_count": float(len(request.items)),
        "total_freight": float(sum(item.freight_value for item in request.items)),
        "total_price": float(sum(item.price for item in request.items)),
        "total_weight_g": total_weight_g(resolved_products),
        "total_volume_cm3": total_volume_cm3(resolved_products),
        "purchase_day_of_week": float(local_purchase.weekday()),
        "purchase_hour": float(local_purchase.hour),
        "customer_state": request.customer_state,
        "origin_state": origin_state(states, seller_ids),
    }


TRAINING_FEATURES_QUERY = """
SELECT
    o.order_id,

    CASE WHEN count(*) FILTER (WHERE zs.latitude IS NULL) > 0
         THEN NULL
         ELSE max(2 * 6371 * asin(sqrt(
             sin(radians(zs.latitude - zc.latitude) / 2) ^ 2
             + cos(radians(zc.latitude)) * cos(radians(zs.latitude))
             * sin(radians(zs.longitude - zc.longitude) / 2) ^ 2
         )))
    END AS distance_km,

    extract(epoch FROM o.estimated_delivery_date - o.purchase_timestamp) / 86400.0
        AS estimated_slack_days,

    count(*)                    AS item_count,
    sum(i.freight_value)        AS total_freight,
    sum(i.price)                AS total_price,

    CASE WHEN count(*) FILTER (WHERE p.weight_g IS NULL) > 0
         THEN NULL
         ELSE sum(p.weight_g)
    END AS total_weight_g,

    CASE WHEN count(*) FILTER (
             WHERE p.length_cm IS NULL OR p.height_cm IS NULL OR p.width_cm IS NULL
         ) > 0
         THEN NULL
         ELSE sum(p.length_cm * p.height_cm * p.width_cm)
    END AS total_volume_cm3,

    extract(isodow FROM o.purchase_timestamp AT TIME ZONE 'America/Sao_Paulo') - 1
        AS purchase_day_of_week,
    extract(hour FROM o.purchase_timestamp AT TIME ZONE 'America/Sao_Paulo')
        AS purchase_hour,

    c.state AS customer_state,
    CASE WHEN count(DISTINCT s.state) = 1 THEN min(s.state) END AS origin_state,

    (o.delivered_customer_date > o.estimated_delivery_date) AS is_late

FROM curated.orders o
JOIN curated.customers c ON c.customer_id = o.customer_id
JOIN curated.order_items i ON i.order_id = o.order_id
JOIN curated.products p ON p.product_id = i.product_id
JOIN curated.sellers s ON s.seller_id = i.seller_id
LEFT JOIN curated.zip_code_locations zc ON zc.zip_code_prefix = c.zip_code_prefix
LEFT JOIN curated.zip_code_locations zs ON zs.zip_code_prefix = s.zip_code_prefix
WHERE o.status = 'delivered'
  AND o.delivered_customer_date IS NOT NULL
GROUP BY o.order_id, o.purchase_timestamp, o.estimated_delivery_date,
         o.delivered_customer_date, c.state
"""


def build_training_features(session: Session) -> pl.DataFrame:
    """Compute the same features as build_features, for every trainable order.

    Per-request extraction issues four queries per order, which is not viable
    for the ninety-six thousand orders in the training set. This produces the
    same features in one pass, and carries the target alongside them.

    Two implementations of one feature will drift. A test compares this output
    against build_features for individual orders, so that drift fails rather
    than silently changing what the model was trained on.
    """
    rows = session.execute(text(TRAINING_FEATURES_QUERY)).mappings().all()
    numeric = [
        "distance_km",
        "estimated_slack_days",
        "item_count",
        "total_freight",
        "total_price",
        "total_weight_g",
        "total_volume_cm3",
        "purchase_day_of_week",
        "purchase_hour",
    ]
    return pl.DataFrame([dict(row) for row in rows]).with_columns(
        pl.col(column).cast(pl.Float64) for column in numeric
    )
