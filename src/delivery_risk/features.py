from math import asin, cos, radians, sin, sqrt

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

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


def seller_locations(session: Session, seller_ids: list[str]) -> dict[str, tuple[float, float]]:
    """Return the coordinates of each seller, keyed by identifier.

    Sellers whose postcode prefix is absent from the catalogue are omitted
    rather than returned as null: seven sellers are in that position (ADR
    0004), and their absence from the mapping is the answer.
    """
    rows = session.execute(
        text(
            """
            SELECT s.seller_id, z.latitude, z.longitude
            FROM curated.sellers s
            JOIN curated.zip_code_locations z
              ON z.zip_code_prefix = s.zip_code_prefix
            WHERE s.seller_id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": list(seller_ids)},
    ).all()

    return {row.seller_id: (float(row.latitude), float(row.longitude)) for row in rows}
