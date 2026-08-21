"""Reconnaissance over the raw Olist CSVs.

Reports structural and integrity facts used to design the database schema.
Read-only: never writes to the dataset, never touches Postgres.
"""

from pathlib import Path

import polars as pl

RAW_DIR = Path("data/raw")

FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv"
}

ZIP_PREFIX_COLUMNS = {
    "customers": "customer_zip_code_prefix",
    "geolocation": "geolocation_zip_code_prefix",
    "sellers": "seller_zip_code_prefix",
}

def load_all() -> dict[str, pl.DataFrame]:
    """Read  every CSV in RAW_DIR, keyed by a short table name.
    
    Postcode prefixes are read as strings: they are codes, not quantitites, and some
    carry leading zeros that interger parsing would discard."""

    tables: dict[str, pl.DataFrame] = {}
    for name, filename in FILES.items():
        overrides = {}
        if name in ZIP_PREFIX_COLUMNS:
            overrides[ZIP_PREFIX_COLUMNS[name]] = pl.String
        tables[name] = pl.read_csv(RAW_DIR / filename, schema_overrides=overrides)
        print(f"Loaded {name}: {tables[name].height} rows")
    return tables

def report_shapes(tables: dict[str, pl.DataFrame]) -> None:
    """Row counts, column counts, dtypes and null counts per table."""
    load_all()

def report_key_candidates(tables: dict[str, pl.DataFrame]) -> None:
    """Uniqueness of each *_id column."""

    print("\n=== KEY CANDIDATES ===")
    for name, df in tables.items():
        id_columns = [c for c in df.columns if c.endswith("_id")]
        if not id_columns:
            continue
        print(f"\n{name} ({df.height} rows)")
        for column in id_columns:
            distinct = df[column].n_unique()
            verdict = "UNIQUE" if distinct == df.height else "NOT UNIQUE"
            print(f"  {column:<40} {distinct:>8} distinct ({verdict})")

def report_referential_integrity(tables: dict[str, pl.DataFrame]) -> None:
    """Count orphan rows for each candidate foreign key, in both directions.

    A child orphan (child row whose parent does not exist) blocks the foreign
    key. A parent without children is not an integrity violation, only a
    completeness fact, but it decides whether the relationship is 1:N or 0:N.
    """
    relationships = [
        ("order_items", "orders", "order_id"),
        ("order_payments", "orders", "order_id"),
        ("order_reviews", "orders", "order_id"),
        ("orders", "customers", "customer_id"),
        ("order_items", "products", "product_id"),
        ("order_items", "sellers", "seller_id"),
    ]

    print("\n=== REFERENTIAL INTEGRITY ===")
    for child, parent, key in relationships:
        child_df = tables[child]
        parent_df = tables[parent]

        orphans = child_df.join(parent_df, on=key, how="anti").height
        childless = parent_df.join(child_df, on=key, how="anti").height

        verdict = "FK ENFORCEABLE" if orphans == 0 else "FK BLOCKED"
        print(f"\n{child}.{key} -> {parent}.{key}")
        print(f"  orphans (child without parent):  {orphans:>7}   {verdict}")
        print(f"  parents without children:        {childless:>7}")


def report_domain_integrity(tables: dict[str, pl.DataFrame]) -> None:
    """Cross order status against the presence of each timestamp.

    Status and timestamps disagree in both directions: orders marked as
    delivered with no delivery date, and cancelled orders that carry one.
    Both are recorded faithfully in `raw` and excluded in `curated`.
    """
    orders = tables["orders"]

    date_columns = [
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]

    print("\n=== DOMAIN INTEGRITY ===")
    print("\nTimestamp presence by order status")

    summary = (
        orders.group_by("order_status")
        .agg(
            pl.len().alias("total"),
            *[
                pl.col(column).is_not_null().sum().alias(column.replace("order_", ""))
                for column in date_columns
            ],
        )
        .sort("total", descending=True)
    )
    print(summary)

    delivered = orders.filter(pl.col("order_status") == "delivered")
    delivered_without_date = delivered.filter(
        pl.col("order_delivered_customer_date").is_null()
    ).height
    cancelled_with_date = orders.filter(
        (pl.col("order_status") == "canceled")
        & pl.col("order_delivered_customer_date").is_not_null()
    ).height

    print("\nContradictions")
    print(f"  delivered without delivery date:  {delivered_without_date:>7}")
    print(f"  cancelled with delivery date:     {cancelled_with_date:>7}")

    trainable = delivered.height - delivered_without_date
    print("\nTraining set definition")
    print("  status == 'delivered' AND delivery date is not null")
    print(f"  eligible rows:                    {trainable:>7}")
    print(f"  share of all orders:              {trainable / orders.height:>7.1%}")

def report_temporal_ordering(tables: dict[str, pl.DataFrame]) -> None:
    """Count violations of the expected chronological order, pair by pair.

    Each pair fails for its own reason and warrants its own decision, so they
    are never aggregated into a single count. The estimated delivery date is
    deliberately excluded: a delivery later than the estimate is the target
    variable, not a violation.
    """
    orders = tables["orders"]

    pairs = [
        ("order_purchase_timestamp", "order_approved_at"),
        ("order_approved_at", "order_delivered_carrier_date"),
        ("order_delivered_carrier_date", "order_delivered_customer_date"),
    ]

    print("\n=== TEMPORAL ORDERING ===")
    print("\nRows where the later timestamp precedes the earlier one")

    for earlier, later in pairs:
        comparable = orders.filter(
            pl.col(earlier).is_not_null() & pl.col(later).is_not_null()
        ).height
        violations = orders.filter(pl.col(later) < pl.col(earlier)).height
        share = violations / comparable if comparable else 0.0

        label = f"{later.replace('order_', '')} < {earlier.replace('order_', '')}"
        print(f"  {label:<52} {violations:>6}  of {comparable:>6}  ({share:.2%})")


def main() -> None:
    tables = load_all()
    report_key_candidates(tables)
    report_referential_integrity(tables)
    report_domain_integrity(tables)
    report_temporal_ordering(tables)


if __name__ == "__main__":
    main()

