# 0005 — Separate person entity from customer records

**Status:** Accepted
**Date:** 2026-08-20

## Context

The `customers` CSV has 99441 rows and a perfect one-to-one correspondence
with `orders`: every order has exactly one customer row and vice versa. The
`customer_id` column is unique per row, but `customer_unique_id` is not:
96096 distinct values across 99441 rows.

The table is therefore not a customer table. Each row is the delivery address
and location attached to a single order. The recurring buyer is a separate
entity that the source data references but does not model.

2997 people placed more than one order; the largest number of orders by one
person is 17.

## Decision

Model the person explicitly in `curated`. A `persons` table keyed on
`customer_unique_id` holds 96096 rows. The existing customer table keeps its
one-to-one relationship with orders and carries a foreign key to `persons`.

## Alternatives considered

**Keep `customers` as the source provides it.** Rejected because the table
name asserts an entity the table does not contain, and because the person is
then reachable only by an ad-hoc aggregation repeated in every query that
needs it.

**Model the person only if a repeat-purchase feature proves useful.**
Rejected: 3.1% recurrence is unlikely to move a calibrated probability, so
this test would fail and leave the naming problem unsolved. The entity is
worth modelling because it exists, not because it predicts.

## Consequences

- `persons` is created by transformation from `raw`, not loaded from a CSV.
  It is the first curated table with no direct source file.
- Repeat-purchase history becomes a join rather than a subquery, should a
  feature ever need it.
- The name of the per-order customer table should be revisited when the
  curated schema is designed as a whole; `customers` remains misleading.
