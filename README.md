# Delivery Risk Service

Predicts, at order creation time, the probability that an order will be
delivered after its estimated delivery date, and exposes that prediction as an
HTTP service.

Built to practise software engineering — service boundaries, persistence,
migrations, testing, containers, CI — on a modelling problem small enough to
stay out of the way.

## What it does

A checkout system posts an order as it is placed. The service validates it,
resolves what the caller does not carry — product weight and dimensions,
seller location, coordinates — from its own database, computes eleven
features, and answers with a probability.

    POST /predict
    {"probability_late": 0.099, "model_version": "logistic-2018-08-29"}

## What the model can and cannot do

It ranks well and it does not know the level.

Across six monthly test windows, each trained on everything before it, AUC
sits between 0.68 and 0.76. An order it scores in the top decile really is
riskier than one in the bottom.

The predicted rate moves between 7.4% and 11.7% while the observed rate moves
between 1.4% and 21.4%. The model beats a constant baseline by 3% to 7% on
Brier score, and loses to it in one window.

| window  | observed | predicted | brier   | baseline | auc   |
|---------|----------|-----------|---------|----------|-------|
| 2018-03 | 21.4%    | 8.6%      | 0.18061 | 0.18666  | 0.601 |
| 2018-04 | 5.3%     | 9.5%      | 0.04907 | 0.05179  | 0.756 |
| 2018-05 | 8.2%     | 9.5%      | 0.07269 | 0.07563  | 0.707 |
| 2018-06 | 1.4%     | 7.4%      | 0.01753 | 0.01892  | 0.729 |
| 2018-07 | 4.5%     | 11.3%     | 0.04734 | 0.04423  | 0.685 |
| 2018-08 | 10.4%    | 11.7%     | 0.09177 | 0.09371  | 0.683 |

Three things were tried against this and none of them worked. System load
features — orders placed in the preceding week and month — helped in the worst
window and hurt four others. Recalibrating on recently observed rates fails
because the previous month does not predict the next: 21.1% precedes 5.3%,
8.4% precedes 1.4%. Gradient boosting is better in March and worse in the last
three windows, degrading as its training set grows.

Whatever drives the monthly swings is not in this dataset. The reasoning is in
`docs/decisions/0021-the-level-of-risk-is-not-predictable.md`.

**Read the probability as a ranking, not as a rate.**

## Data

Source: Brazilian E-Commerce Public Dataset by Olist
<https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>

Download requires a Kaggle account. Extract all nine CSVs into `data/raw/`,
which is gitignored.

## Architecture

Two schemas. `raw` mirrors the source files, every column text, no domain
constraints, so ingestion never fails on dirty values. `curated` holds the
typed, constrained domain model, built by a transformation that reports every
row it excludes and why.

Of 99441 source orders, 99412 reach `curated` and 96447 are eligible for
training.

Features are computed twice: per request in Python for the service, and in
bulk SQL for training. A test compares the two on the same order, so drift
between them fails rather than silently changing what the model is served.

Every schema decision — which columns are nullable, which foreign keys can be
enforced, which rows are excluded — is traceable to a measurement in
`scripts/recon.py` and recorded in `docs/decisions/`.

## Setup

Requires Docker and [uv](https://docs.astral.sh/uv/).

    cp .env.example .env
    docker compose up -d db
    uv sync
    uv run alembic upgrade head

Then load the data and train:

    uv run python scripts/recon.py           # profile the source files
    uv run python scripts/load_raw.py        # CSVs into raw
    uv run python scripts/transform.py       # raw into curated
    uv run python scripts/train.py           # score six monthly windows
    uv run python scripts/register_model.py  # write models/ for the service

## Running the service

    docker compose up -d --build

Or locally, with reload:

    docker compose up -d db
    uv run uvicorn delivery_risk.api.app:app --reload

Interactive documentation is at <http://127.0.0.1:8000/docs>. Without a model
in `models/`, the service starts and answers with a constant — `/health`
reports which model is loaded.

## Development

    uv run ruff format .
    uv run ruff check .
    uv run mypy src/
    uv run pytest

Integration tests start a throwaway Postgres through testcontainers, migrate
it and seed it, so they need Docker but not a loaded database.

## Known gaps

- `docker compose up` does not run migrations; a fresh volume gives a database
  the service cannot query
- CI runs lint, types and tests, but does not build the image or exercise
  Compose
- Product category is available and unused as a feature

## Decisions

Twenty-two decision records in `docs/decisions/`, one per decision, each
stating the alternatives considered and why they were rejected.
