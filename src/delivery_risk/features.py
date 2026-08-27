from math import asin, cos, radians, sin, sqrt

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from delivery_risk.api.schemas import PredictionRequest

EARTH_RADIUS_KM = 6371.0


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


def build_features(session: Session, request: PredictionRequest) -> dict[str, float | None]:
    """Turn a request into the features the model expects."""

    prefix = request.customer_zip_code_prefix
    seller_ids = [item.seller_id for item in request.items]

    customer = customer_location(session, prefix)
    sellers = seller_locations(session, seller_ids)

    distance = distance_km(customer, list(sellers.values()))

    return {"distance_km": distance}
