# Delivery Risk Service

Predicts, at order creation time, the probability that an order will be
delivered after its estimated delivery date, and exposes that prediction as an
HTTP service.

## Status

The data layer is complete: ingestion, schema and transformation. The service
runs with a constant model behind the prediction interface — the HTTP contract
is settled before any model exists, so the model can be swapped without
touching the API. Feature extraction and the trained model are not yet built.

## Data

Source: Brazilian E-Commerce Public Dataset by Olist
<https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>

Download requires a Kaggle account. Extract all nine CSVs into `data/raw/`:

    olist_customers_dataset.csv
    olist_geolocation_dataset.csv
    olist_order_items_dataset.csv
    olist_order_payments_dataset.csv
    olist_order_reviews_dataset.csv
    olist_orders_dataset.csv
    olist_products_dataset.csv
    olist_sellers_dataset.csv
    product_category_name_translation.csv

The `data/` directory is gitignored.

## Architecture

The database holds two schemas. `raw` mirrors the source files faithfully,
with every column as text and no domain constraints, so ingestion never fails
on dirty values. `curated` holds the typed, constrained domain model, built
from `raw` by an explicit transformation that reports every row it excludes
and why.

Of 99441 source orders, 99412 reach `curated`; 96447 are eligible for
training, of which 8.11% were delivered late.

Every schema decision — which columns are nullable, which foreign keys can be
enforced, which rows are excluded — is traceable to a measurement in
`scripts/recon.py`, and recorded in `docs/decisions/`.

## Setup

Requires Docker and [uv](https://docs.astral.sh/uv/).

    cp .env.example .env
    docker compose up -d
    uv sync
    uv run alembic upgrade head

## Usage

    uv run python scripts/recon.py      # profile the source files
    uv run python scripts/load_raw.py   # CSVs into raw
    uv run python scripts/transform.py  # raw into curated

## Running the service

    docker compose up -d
    uv run uvicorn delivery_risk.api.app:app --reload

Interactive documentation is at <http://127.0.0.1:8000/docs>

## Development

    uv run ruff format .
    uv run ruff check .
    uv run mypy src/

## Decisions

Architectural decisions are recorded in `docs/decisions/`, one file per
decision, each stating the alternatives considered and why they were rejected.
