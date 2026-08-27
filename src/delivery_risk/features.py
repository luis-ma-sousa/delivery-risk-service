from math import asin, cos, radians, sin, sqrt

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
