# 0010 — Reviews are excluded from the curated layer

**Status:** Accepted
**Date:** 2026-08-22

## Context

The source data includes 99224 order reviews. They are structurally sound —
zero referential orphans, and the pair `(review_id, order_id)` is unique — but
they arrive after delivery has completed.

The service predicts, at order creation time, whether an order will be
delivered late. A review cannot inform that prediction: it does not exist when
the prediction is made. Using one as a feature would be leakage.

## Decision

`curated` holds no review table. Reviews remain in `raw`, faithfully mirrored
like every other source file.

## Alternatives considered

**Carry reviews into `curated` for completeness.** Rejected: the layer would
gain a table with types, constraints and a foreign key, none of which any
consumer would read. `curated` is the domain model for this service, not a
general-purpose copy of the source.

**Keep reviews for a future sentiment feature.** Rejected on the same leakage
grounds. A feature computed after the event cannot serve a prediction made
before it, whatever its content.

## Consequences

- `curated` has nine tables, as `raw` does, but not the same nine: reviews are
  dropped and a person table is added (ADR 0005).
- Reviews remain queryable in `raw` should a different question ever need them.
- The 88% null rate on review titles and 59% on comment bodies is no longer a
  problem this layer has to model.
