"""Tests for feature computation."""

from delivery_risk.features import distance_km, haversine_km


def test_distance_between_a_point_and_itself_is_zero() -> None:
    assert haversine_km(-23.55, -46.63, -23.55, -46.63) == 0.0


def test_known_distance_sao_paulo_to_rio() -> None:
    distance = haversine_km(-23.55, -46.63, -22.91, -43.17)

    assert 355 < distance < 365


def test_distance_is_symmetric() -> None:
    there = haversine_km(-23.55, -46.63, -22.91, -43.17)
    back = haversine_km(-22.91, -43.17, -23.55, -46.63)

    assert there == back


def test_longitude_shrinks_away_from_the_equator() -> None:
    """One degree of longitude spans less ground at higher latitudes.

    This is what a naive Pythagorean distance would get wrong, so it is worth
    asserting rather than assuming.
    """
    at_equator = haversine_km(0.0, 0.0, 0.0, 1.0)
    far_south = haversine_km(-60.0, 0.0, -60.0, 1.0)

    assert far_south < at_equator / 1.5


def test_distance_to_a_single_seller() -> None:
    sao_paulo = (-23.55, -46.63)
    rio = (-22.91, -43.17)

    assert distance_km(sao_paulo, [rio]) == haversine_km(-23.55, -46.63, -22.91, -43.17)


def test_distance_uses_the_furthest_seller() -> None:
    sao_paulo = (-23.55, -46.63)
    campinas = (-22.90, -47.06)
    rio = (-22.91, -43.17)

    with_both = distance_km(sao_paulo, [campinas, rio])
    rio_only = distance_km(sao_paulo, [rio])

    assert with_both == rio_only


def test_distance_is_unknown_when_a_seller_has_no_location() -> None:
    sao_paulo = (-23.55, -46.63)
    rio = (-22.91, -43.17)

    assert distance_km(sao_paulo, [rio, None]) is None


def test_distance_is_unknown_when_the_customer_has_no_location() -> None:
    rio = (-22.91, -43.17)

    assert distance_km(None, [rio]) is None
