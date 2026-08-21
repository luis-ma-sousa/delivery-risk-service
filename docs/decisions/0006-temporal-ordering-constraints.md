# 0006 — Temporal ordering constraints

**Status:** Accepted
**Date:** 2026-08-21

## Context

Orders carry four operational timestamps: purchase, payment approval, handover
to the carrier, and delivery to the customer. The obvious expectation is that
they occur in that order. Measured against the source data, each pair behaves
differently:

- `approved_at >= purchase_timestamp`: 0 violations.
- `delivered_carrier_date >= approved_at`: 1359 violations (1.4% of
  comparable rows).
- `delivered_customer_date >= delivered_carrier_date`: 23 violations (0.02%).

The estimated delivery date is excluded from this analysis. A delivery later
than the estimate is the target variable, not a violation.

## Decision

Constraints are decided per pair, in `curated` only.

**Purchase before approval** is enforced as a `CHECK` constraint.

**Approval before carrier handover is not enforced.** The 1359 violations are
not corrupt data; the expectation was wrong. Approval timestamps originate
from the payment gateway and handover timestamps from logistics. Sellers
despatch without waiting for payment confirmation to be recorded, so the two
sequences are genuinely independent.

**Carrier handover before customer delivery** is enforced, after excluding the
23 violating rows during transformation. Delivery preceding despatch is
physically impossible and is treated as source error.

## Alternatives considered

**Enforce the full chain.** Rejected: it would exclude 1359 valid orders to
preserve an assumption the business does not hold.

**Enforce nothing and filter at query time.** Rejected for the reasons in
ADR 0001: integrity decisions buried in query code are invisible and repeated.

**Keep the 23 impossible rows and handle them as a modelling concern.**
Rejected: they are not a modelling edge case but a data error, and a `curated`
layer that carries known-impossible rows is not curated.

## Consequences

- `curated` holds 23 fewer orders than `raw` on this account alone. The delta
  between layers is a quality signal, as established in ADR 0001.
- Any feature derived from the interval between approval and carrier handover
  may be negative. Feature code must handle that, or the interval must be
  discarded.
- The unenforced pair is documented here rather than silently omitted, so the
  absence of the constraint is traceable to a measurement.
