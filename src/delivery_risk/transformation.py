"""Transform `raw` into `curated`.

Every exclusion here is traceable to a decision record, and every one is
reported: a row dropped in silence is a row nobody knows about (ADR 0001).
"""

import polars as pl
from sqlalchemy import insert, text
from sqlalchemy.orm import Session

from delivery_risk.models import Person, ZipCodeLocation, CategoryTranslation, Seller

BRAZIL_BOUNDS = {
    "lat_min": -34.0,
    "lat_max": 5.3,
    "lng_min": -74.0,
    "lng_max": -34.8,
}

MISSING_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "kitchen_portables_and_food_preparers",
}

BATCH_SIZE = 10_000


def read_frame(session: Session, query: str) -> pl.DataFrame:
    """Run a query and return the result as a Polars frame."""
    rows = session.execute(text(query)).mappings().all()
    return pl.DataFrame([dict(row) for row in rows])


def write_frame(session: Session, model: type, frame: pl.DataFrame) -> int:
    """Insert a frame into a curated table in batches."""
    rows = frame.to_dicts()
    for start in range(0, len(rows), BATCH_SIZE):
        session.execute(insert(model), rows[start : start + BATCH_SIZE])
    return len(rows)

def truncate(session: Session, model: type) -> None:
    """Remove every row from a curated table before repopulating it.

    Transformation is repeatable by construction: each run leaves `curated`
    reflecting `raw` as it is now, not as it was plus what changed.
    """
    table = model.__table__
    session.execute(text(f"TRUNCATE TABLE {table.schema}.{table.name} CASCADE"))

def transform_zip_code_locations(session: Session) -> None:
    """Collapse the geolocation catalogue to one coordinate per prefix.

    Points outside the Brazil bounding box are discarded before aggregation,
    and the representative point is the median rather than the mean: the
    distribution is contaminated by outliers thousands of kilometres out, which
    a mean would propagate into the centroid (ADR 0003).
    """
    print("\n=== zip_code_locations ===")

    geo = read_frame(
        session,
        """
        SELECT geolocation_zip_code_prefix AS zip_code_prefix,
               geolocation_lat AS lat,
               geolocation_lng AS lng
        FROM raw.geolocation
        """,
    )

    parsed = geo.with_columns(
        pl.col("lat").cast(pl.Float64, strict=False),
        pl.col("lng").cast(pl.Float64, strict=False),
    )
    unparseable = parsed.filter(
        pl.col("lat").is_null() | pl.col("lng").is_null()
    ).height

    inside = parsed.filter(
        pl.col("lat").is_between(BRAZIL_BOUNDS["lat_min"], BRAZIL_BOUNDS["lat_max"])
        & pl.col("lng").is_between(BRAZIL_BOUNDS["lng_min"], BRAZIL_BOUNDS["lng_max"])
    )

    prefixes_before = geo["zip_code_prefix"].n_unique()

    locations = (
        inside.group_by("zip_code_prefix")
        .agg(
            pl.col("lat").median().alias("latitude"),
            pl.col("lng").median().alias("longitude"),
        )
        .sort("zip_code_prefix")
    )

    dispersion = inside.group_by("zip_code_prefix").agg(
        (pl.col("lat").max() - pl.col("lat").min()).alias("lat_span")
    )
    incoherent = dispersion.filter(pl.col("lat_span") > 1.0).height

    print(f"  source points:              {geo.height:>8}")
    print(f"  unparseable coordinates:    {unparseable:>8}")
    print(f"  outside Brazil, discarded:  {geo.height - inside.height - unparseable:>8}")
    print(f"  prefixes lost entirely:     {prefixes_before - locations.height:>8}")
    print(f"  prefixes spanning over 1 degree of latitude: {incoherent} "
          f"({incoherent / locations.height:.2%}) — kept, see ADR 0003")

    truncate(session, ZipCodeLocation)
    written = write_frame(session, ZipCodeLocation, locations)
    print(f"  written:                    {written:>8}")

def transform_persons(session: Session) -> None:
    """Extract the distinct recurring buyers from the customer records.

    The source customer table holds one row per order, with 96096 distinct
    people across 99441 rows. The person is an entity the source references
    but does not model (ADR 0005).
    """
    print("\n=== persons ===")

    persons = read_frame(
        session,
        """
        SELECT DISTINCT customer_unique_id AS person_id
        FROM raw.customers
        """,
    )

    source_rows = session.execute(
        text("SELECT count(*) FROM raw.customers")
    ).scalar_one()

    print(f"  source customer rows:       {source_rows:>8}")
    print(f"  distinct people:            {persons.height:>8}")

    truncate(session, Person)
    written = write_frame(session, Person, persons)
    print(f"  written:                    {written:>8}")

MISSING_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "kitchen_portables_and_food_preparers",
}


def transform_category_translation(session: Session) -> None:
    """Copy the category translations, completing the two the source omits.

    Products carry 73 distinct categories and the source translates 71. The
    two missing entries are supplied here so the foreign key from products can
    be declared; their English names are ours, not Olist's (ADR 0012).
    """
    print("\n=== category_translation ===")

    source = read_frame(
        session,
        """
        SELECT product_category_name AS category_name,
               product_category_name_english AS category_name_english
        FROM raw.category_translation
        """,
    )

    supplied = pl.DataFrame(
        {
            "category_name": list(MISSING_TRANSLATIONS.keys()),
            "category_name_english": list(MISSING_TRANSLATIONS.values()),
        }
    )

    translations = pl.concat([source, supplied]).sort("category_name")

    print(f"  translations in source:     {source.height:>8}")
    print(f"  supplied here (ADR 0012):   {supplied.height:>8}")

    truncate(session, CategoryTranslation)
    written = write_frame(session, CategoryTranslation, translations)
    print(f"  written:                    {written:>8}")

def transform_sellers(session: Session) -> None:
    """Copy sellers, resolving their postcode against the location catalogue.

    Seven sellers carry a prefix the catalogue does not cover. Their location
    is set to null rather than dropped: a seller exists independently of
    whether we can place them on a map (ADR 0004).
    """
    print("\n=== sellers ===")

    sellers = read_frame(
        session,
        """
        SELECT s.seller_id,
               z.zip_code_prefix,
               s.seller_city AS city,
               s.seller_state AS state
        FROM raw.sellers s
        LEFT JOIN curated.zip_code_locations z
               ON z.zip_code_prefix = s.seller_zip_code_prefix
        """,
    )

    unlocated = sellers.filter(pl.col("zip_code_prefix").is_null()).height

    print(f"  source rows:                {sellers.height:>8}")
    print(f"  without a known location:   {unlocated:>8}")

    truncate(session, Seller)
    written = write_frame(session, Seller, sellers)
    print(f"  written:                    {written:>8}")