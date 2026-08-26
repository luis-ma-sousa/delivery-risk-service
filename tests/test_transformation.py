import polars as pl

from delivery_risk.transformation import within_brazil


def test_bounding_box() -> None:
    """Test that the bounding box is computed correctly."""
    # Create a DataFrame with known coordinates
    # São Paulo (-23.55, -43.63)
    # Braga (PT) (41.6, -8.4)
    df = pl.DataFrame({"latitude": [-23.55, 41.6], "longitude": [-43.63, -8.4]})

    inside = within_brazil(df, "latitude", "longitude")

    assert inside.height == 1, "Only São Paulo should be inside the bounding box"
    assert inside["latitude"][0] == -23.55
    assert inside["longitude"][0] == -43.63
