"""Load the source CSVs into the `raw` schema.

Every column is read and written as text, per ADR 0009: nothing between the
file and the database interprets a value. Each table is truncated before
loading, so a run always leaves `raw` mirroring the files on disk.
"""

from pathlib import Path
from typing import cast

import polars as pl
from sqlalchemy import Table, insert, inspect, text
from sqlalchemy.orm import Session

from delivery_risk.models import (
    Base,
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

RAW_DIR = Path("data/raw")
BATCH_SIZE = 10_000

SOURCES = [
    (RawCustomer, "olist_customers_dataset.csv"),
    (RawGeolocation, "olist_geolocation_dataset.csv"),
    (RawOrderItem, "olist_order_items_dataset.csv"),
    (RawOrderPayment, "olist_order_payments_dataset.csv"),
    (RawOrderReview, "olist_order_reviews_dataset.csv"),
    (RawOrder, "olist_orders_dataset.csv"),
    (RawProduct, "olist_products_dataset.csv"),
    (RawSeller, "olist_sellers_dataset.csv"),
    (RawCategoryTranslation, "product_category_name_translation.csv"),
]


def load_csv(filename: str) -> pl.DataFrame:
    """Read a source CSV with every column as text."""
    return pl.read_csv(RAW_DIR / filename, infer_schema_length=0)


def truncate(session: Session, model: type[Base]) -> None:
    """Remove every row from a table before repopulating it."""
    table = cast(Table, inspect(model).local_table)
    session.execute(text(f"TRUNCATE TABLE {table.schema}.{table.name}"))


def insert_rows(session: Session, model: type[Base], frame: pl.DataFrame) -> int:
    """Insert a frame in batches, returning the number of rows written."""
    rows = frame.to_dicts()
    for start in range(0, len(rows), BATCH_SIZE):
        session.execute(insert(model), rows[start : start + BATCH_SIZE])
    return len(rows)


def ingest(session: Session) -> None:
    """Load every source CSV into `raw`, replacing what is there."""
    for model, filename in SOURCES:
        frame = load_csv(filename)
        truncate(session, model)
        written = insert_rows(session, model, frame)
        print(f"{model.__tablename__:<24} {written:>8} rows")
