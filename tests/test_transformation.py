import polars as pl
from delivery_risk.transformation import BRAZIL_BOUNDS

def test_bounding_box() -> None:
     """Test that the bounding box is computed correctly."""
     # Create a DataFrame with known coordinates like São Paulo (-23.55, -43.63) and Braga (PT) (41.6, -8.4)
     df = pl.DataFrame({
          "latitude": [-23.55, 41.6],
          "longitude": [-43.63, -8.4]
     })

     inside = df.filter(
          pl.col("latitude").is_between(BRAZIL_BOUNDS["lat_min"], BRAZIL_BOUNDS["lat_max"]) &
          pl.col("longitude").is_between(BRAZIL_BOUNDS["lng_min"], BRAZIL_BOUNDS["lng_max"])
    )

     assert inside.height == 1, "Only São Paulo should be inside the bounding box"
     assert inside["latitude"][0] == -23.55
     assert inside["longitude"][0] == -43.63
