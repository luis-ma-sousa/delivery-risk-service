# 0001 — Two-layer schema: raw and curated

**Status:** Accepted
**Date:** 2026-08-19

## Context

The Olist CSVs contain rows that violate domain expectations: orders marked
as delivered without a delivery timestamp, and timestamps that are out of
chronological order. Enforcing constraints directly on ingestion would abort
the load; ignoring them would silently discard evidence.

## Decision

Two schemas in the same database. `raw` mirrors the CSVs faithfully, with no
domain constraints. `curated` holds constrained, analysis-ready tables,
populated by an explicit transformation step from `raw`.

## Alternatives considered

**Single constrained layer with a rejects table.** Cheaper for a 100k-row
dataset. Rejected because the rejects table is an ad-hoc mechanism that
duplicates what a raw layer does properly, and because the reasons for
rejection would have to be encoded by hand.

**Single permissive layer, filtering downstream.** Rejected because it pushes
every integrity decision into query code, where it is invisible and repeated.

## Consequences

- Ingestion does not fail on dirty values; failures surface in transformation.
- `raw` enforces entity integrity only: a natural key may not repeat. Domain
  and referential integrity are deferred to `curated`. A duplicated key aborts
  the load, which is intended — it signals a fault upstream rather than dirty
  data in the source.
- Every exclusion is expressed as SQL, reviewable and re-runnable.
- Row counts differ between layers. This is expected, and the delta is itself
  a quality signal worth reporting.
