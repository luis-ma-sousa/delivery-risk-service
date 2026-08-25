# 0013 — Contradictory orders are excluded from curated

**Status:** Accepted
**Date:** 2026-08-25

## Context

Two groups of orders contradict themselves, in different ways.

Twenty-three orders record delivery to the customer before handover to the
carrier. This is physically impossible and is source error.

Six orders carry status `canceled` alongside a delivery date. This is not
impossible — a return recorded as a cancellation would produce it — but the
final status and the delivery record disagree, and nothing in the data says
which is correct.

A further eight orders are marked `delivered` with no delivery date. They are
not excluded here: they are simply ineligible for training, and the filter
that selects the training set removes them without a rule of its own.

## Decision

Both groups are excluded during transformation. `curated` contains 99412
orders to `raw`'s 99441.

## Alternatives considered

**Keep the six cancelled-and-delivered orders.** No constraint rejects them,
and the training filter excludes them anyway on status. Rejected on the
principle that `curated` should not hold rows known to contradict themselves,
whether or not any current consumer would read them.

**Keep the twenty-three and treat them as a modelling edge case.** Rejected:
they are source error, not an edge case, and a curated layer carrying
known-impossible rows is not curated.

## Consequences

- Twenty-nine orders exist in `raw` and not in `curated`. Their items and
  payments are excluded with them, since a line cannot reference an order that
  is not there.
- The exclusion is reported by the transformation, so the delta between layers
  stays visible without reading this document.
- The check constraint on delivery order in `curated.orders` would have
  rejected the twenty-three regardless. Excluding them explicitly means the
  transformation reports a count rather than aborting.
