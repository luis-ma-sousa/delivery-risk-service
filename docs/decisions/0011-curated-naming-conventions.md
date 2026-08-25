# 0011 — Naming conventions in the curated layer

**Status:** Accepted
**Date:** 2026-08-22

## Context

The source CSVs prefix most column names with their table: `order_status`,
`product_weight_g`, `seller_zip_code_prefix`. Inside a table that already
carries that name, the prefix is redundant. The source also contains a
misspelling, `lenght`, repeated across two columns.

`raw` mirrors the source exactly (ADR 0009), so any correction belongs to
`curated`.

## Decision

In `curated`, a column does not repeat the name of its table.
`orders.status`, `products.weight_g`, `sellers.zip_code_prefix`.

Key columns are the exception and keep their full name: `order_id`,
`customer_id`, `product_id`, `seller_id`. They appear in several tables, and
consistency across them is worth more than brevity within one.

`lenght` is spelled `length`.

## Alternatives considered

**Keep source names throughout.** Rejected: it makes the transformation a
pure copy at the cost of carrying redundancy and a typo into the layer that is
meant to be the domain model.

**Rename keys as well, so `orders.id` and `order_items.order_id`.** Rejected:
the same value would then have two names depending on which side of a join it
sits, which is harder to read than the redundancy it removes.

## Consequences

- The transformation from `raw` to `curated` includes an explicit column
  mapping. It is no longer a mechanical copy, which is the point.
- Queries written against `raw` do not transfer unchanged to `curated`.
- Anyone comparing the two layers needs this document to know that
  `raw.orders.order_status` and `curated.orders.status` are the same column.
