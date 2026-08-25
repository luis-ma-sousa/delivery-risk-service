"""Transform `raw` into `curated`.

Every exclusion here is traceable to a decision record, and every one is
reported: a row dropped in silence is a row nobody knows about (ADR 0001).
"""

import polars as pl
from sqlalchemy import insert, text
from sqlalchemy.orm import Session

from delivery_risk.models import (
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

DATE_COLUMNS = [
    "purchase_timestamp",
    "approved_at",
    "delivered_carrier_date",
    "delivered_customer_date",
    "estimated_delivery_date",
]

SAO_PAULO = "America/Sao_Paulo"


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
    unparseable = parsed.filter(pl.col("lat").is_null() | pl.col("lng").is_null()).height

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
    print(
        f"  prefixes spanning over 1 degree of latitude: {incoherent} "
        f"({incoherent / locations.height:.2%}) — kept, see ADR 0003"
    )

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

    source_rows = session.execute(text("SELECT count(*) FROM raw.customers")).scalar_one()

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


def transform_products(session: Session) -> None:
    """Copy products, converting their numeric attributes from text.

    610 products carry no descriptive metadata at all — category, name length,
    description length and photo count are null together — and two have no
    physical dimensions. Both groups are kept: absent metadata may itself
    predict something.

    The category foreign key never fails to resolve, because the two
    translations the source omits are supplied in `curated` (ADR 0012).
    """
    print("\n=== products ===")

    products = read_frame(
        session,
        """
        SELECT product_id,
               product_category_name AS category_name,
               product_name_lenght AS name_length,
               product_description_lenght AS description_length,
               product_photos_qty AS photos_qty,
               product_weight_g AS weight_g,
               product_length_cm AS length_cm,
               product_height_cm AS height_cm,
               product_width_cm AS width_cm
        FROM raw.products
        """,
    )

    numeric_columns = [
        "name_length",
        "description_length",
        "photos_qty",
        "weight_g",
        "length_cm",
        "height_cm",
        "width_cm",
    ]

    null_before = {column: products[column].null_count() for column in numeric_columns}

    converted = products.with_columns(
        pl.col(column).cast(pl.Int64, strict=False) for column in numeric_columns
    )

    unparseable = sum(
        converted[column].null_count() - null_before[column] for column in numeric_columns
    )

    print(f"  source rows:                {products.height:>8}")
    print(f"  without a category:         {converted['category_name'].null_count():>8}")
    print(f"  values that failed to parse:{unparseable:>8}")

    truncate(session, Product)
    written = write_frame(session, Product, converted)
    print(f"  written:                    {written:>8}")


def transform_customers(session: Session) -> None:
    """Copy the per-order customer records, linked to person and location.

    Each row is the delivery address of a single order, not a customer: the
    relationship to orders is 1:1. The person behind it is referenced through
    `person_id` (ADR 0005).

    278 rows carry a prefix the location catalogue does not cover; their
    location is null, the row is kept (ADR 0004).
    """
    print("\n=== customers ===")

    customers = read_frame(
        session,
        """
        SELECT c.customer_id,
               c.customer_unique_id AS person_id,
               z.zip_code_prefix,
               c.customer_city AS city,
               c.customer_state AS state
        FROM raw.customers c
        LEFT JOIN curated.zip_code_locations z
               ON z.zip_code_prefix = c.customer_zip_code_prefix
        """,
    )

    unlocated = customers.filter(pl.col("zip_code_prefix").is_null()).height

    print(f"  source rows:                {customers.height:>8}")
    print(f"  without a known location:   {unlocated:>8}")

    truncate(session, Customer)
    written = write_frame(session, Customer, customers)
    print(f"  written:                    {written:>8}")


def transform_orders(session: Session) -> None:
    """Copy orders, parsing timestamps and excluding contradictory rows.

    Timestamps are naive in the source and are read as local time in
    America/Sao_Paulo (ADR 0002). Ambiguous times, which occur twice on a
    fall-back date, resolve to the earlier instant; times inside a
    spring-forward gap do not exist and become null. Neither case arises in
    this dataset, but the policy is explicit rather than left to the library.

    Two groups are excluded (ADR 0013): orders delivered before despatch, and
    cancelled orders carrying a delivery date.
    """
    print("\n=== orders ===")

    orders = read_frame(
        session,
        """
        SELECT order_id,
               customer_id,
               order_status AS status,
               order_purchase_timestamp AS purchase_timestamp,
               order_approved_at AS approved_at,
               order_delivered_carrier_date AS delivered_carrier_date,
               order_delivered_customer_date AS delivered_customer_date,
               order_estimated_delivery_date AS estimated_delivery_date
        FROM raw.orders
        """,
    )

    parsed = orders.with_columns(
        pl.col(column).str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False) for column in DATE_COLUMNS
    )
    unparseable = sum(
        parsed[column].null_count() - orders[column].null_count() for column in DATE_COLUMNS
    )

    aware = parsed.with_columns(
        pl.col(column).dt.replace_time_zone(SAO_PAULO, ambiguous="earliest", non_existent="null")
        for column in DATE_COLUMNS
    )
    lost_to_dst = sum(
        aware[column].null_count() - parsed[column].null_count() for column in DATE_COLUMNS
    )

    impossible = aware.filter(
        pl.col("delivered_customer_date") < pl.col("delivered_carrier_date")
    ).height
    cancelled_delivered = aware.filter(
        (pl.col("status") == "canceled") & pl.col("delivered_customer_date").is_not_null()
    ).height

    kept = aware.filter(
        (
            pl.col("delivered_customer_date").is_null()
            | pl.col("delivered_carrier_date").is_null()
            | (pl.col("delivered_customer_date") >= pl.col("delivered_carrier_date"))
        )
        & ~((pl.col("status") == "canceled") & pl.col("delivered_customer_date").is_not_null())
    )

    print(f"  source rows:                {orders.height:>8}")
    print(f"  timestamps unparseable:     {unparseable:>8}")
    print(f"  timestamps lost to DST gap: {lost_to_dst:>8}")
    print(f"  delivered before despatch:  {impossible:>8}  excluded (ADR 0013)")
    print(f"  cancelled with delivery:    {cancelled_delivered:>8}  excluded (ADR 0013)")

    truncate(session, Order)
    written = write_frame(session, Order, kept)
    print(f"  written:                    {written:>8}")


def transform_order_items(session: Session) -> None:
    """Copy order lines, keeping only those whose order survived.

    The inner join against `curated.orders` drops lines belonging to the
    twenty-nine orders excluded by ADR 0013: a line cannot reference an order
    that is not there.

    `order_item_id` becomes an integer here. It counts items within an order,
    running from 1 to 21, and is not a global identifier despite its name.
    """
    print("\n=== order_items ===")

    items = read_frame(
        session,
        """
        SELECT i.order_id,
               i.order_item_id,
               i.product_id,
               i.seller_id,
               i.shipping_limit_date,
               i.price,
               i.freight_value
        FROM raw.order_items i
        JOIN curated.orders o ON o.order_id = i.order_id
        """,
    )

    source_rows = session.execute(text("SELECT count(*) FROM raw.order_items")).scalar_one()

    converted = items.with_columns(
        pl.col("order_item_id").cast(pl.Int64, strict=False),
        pl.col("price").cast(pl.Float64, strict=False),
        pl.col("freight_value").cast(pl.Float64, strict=False),
        pl.col("shipping_limit_date").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False),
    ).with_columns(
        pl.col("shipping_limit_date").dt.replace_time_zone(
            SAO_PAULO, ambiguous="earliest", non_existent="null"
        )
    )

    unparseable = converted.filter(
        pl.col("order_item_id").is_null()
        | pl.col("price").is_null()
        | pl.col("freight_value").is_null()
        | pl.col("shipping_limit_date").is_null()
    ).height

    print(f"  source rows:                {source_rows:>8}")
    print(f"  dropped with excluded orders:{source_rows - items.height:>7}")
    print(f"  values that failed to parse:{unparseable:>8}")

    truncate(session, OrderItem)
    written = write_frame(session, OrderItem, converted)
    print(f"  written:                    {written:>8}")


def transform_order_payments(session: Session) -> None:
    """Copy payments, keeping only those whose order survived.

    One delivered order has no payment record at all: the relationship is 0:N,
    not 1:N, and nothing here requires a payment to exist.
    """
    print("\n=== order_payments ===")

    payments = read_frame(
        session,
        """
        SELECT p.order_id,
               p.payment_sequential,
               p.payment_type,
               p.payment_installments AS installments,
               p.payment_value AS value
        FROM raw.order_payments p
        JOIN curated.orders o ON o.order_id = p.order_id
        """,
    )

    source_rows = session.execute(text("SELECT count(*) FROM raw.order_payments")).scalar_one()

    converted = payments.with_columns(
        pl.col("payment_sequential").cast(pl.Int64, strict=False),
        pl.col("installments").cast(pl.Int64, strict=False),
        pl.col("value").cast(pl.Float64, strict=False),
    )

    unparseable = converted.filter(
        pl.col("payment_sequential").is_null()
        | pl.col("installments").is_null()
        | pl.col("value").is_null()
    ).height

    print(f"  source rows:                {source_rows:>8}")
    print(f"  dropped with excluded orders:{source_rows - payments.height:>7}")
    print(f"  values that failed to parse:{unparseable:>8}")

    truncate(session, OrderPayment)
    written = write_frame(session, OrderPayment, converted)
    print(f"  written:                    {written:>8}")
