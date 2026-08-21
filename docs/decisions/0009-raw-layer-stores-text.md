# 0009 — The raw layer stores everything as text

**Status:** Accepted
**Date:** 2026-08-21

## Context

ADR 0001 established that `raw` mirrors the source CSVs faithfully and that
ingestion must never fail on dirty input. It did not settle what "faithfully"
means for column types. Two readings are defensible: store every column as
text and defer all parsing, or use native types where the source is
unambiguous — numeric for prices, `timestamptz` for dates — while still
declining domain constraints.

There is no settled industry answer here; both patterns are in common use.

## Decision

Every column in `raw` is `TEXT`. Numbers, dates and identifiers alike. All
type conversion happens in the transformation into `curated`.

## Alternatives considered

**Native types where the source is unambiguous.** Rejected because a typed
column can reject a value, and a rejected value leaves no trace. A malformed
date would either abort the load or be silently dropped, and in both cases the
evidence that a bad value existed is gone. With text columns the row lands,
and the transformation rejects it with a count and a stated reason — which is
what ADR 0001 asked for.

## Consequences

- `raw` is not usefully queryable on its own. Comparing dates or numbers
  requires an explicit cast in every query. This is a real cost and is the
  price of fidelity.
- Every conversion is written once, in the transformation, where it is visible
  and testable. Nothing is decided implicitly by the database driver.
- Malformed values are counted rather than lost, so the delta between layers
  remains the quality signal established in ADR 0001.
- Storage is larger than it would be with native types. At this dataset size
  the difference is immaterial.
