# 0014 — Prediction point and feature availability

**Status:** Accepted
**Date:** 2026-08-26

## Context

The service predicts, at order creation time, whether an order will be
delivered after its estimated date. The dataset records each order in its final
state, so most of what it contains describes the future relative to that
moment. Any column written after creation is unavailable to the model, and
using one would be leakage — the model would appear to work and would fail on
the first order it had never seen.

The boundary is not obvious from the schema. Nothing marks a column as
after-the-fact, and several columns that seem available at creation are not.

## Decision

Only the following are available to the model:

**Order** — `order_id`, `customer_id`, `purchase_timestamp`,
`estimated_delivery_date`.

**Customer** — city, state, postcode prefix, and the coordinates derived from
it.

**Items** — `product_id`, `seller_id`, `price`, `freight_value`, and the
count and composition of the lines.

**Products** — category, weight, dimensions, and the descriptive metadata,
including its absence.

**Payment** — `payment_type`, `installments`, `value`.

**Sellers** — city, state, postcode prefix, and the coordinates derived from
it.

Everything else is excluded:

| Column | Why it is unavailable |
|---|---|
| `status` | Every order is `created` or `processing` at this point. Any later value describes the outcome. |
| `approved_at` | Payment approval arrives after creation, and is null for 160 orders. |
| `delivered_carrier_date` | Despatch happens after creation. |
| `delivered_customer_date` | The outcome itself. |
| `shipping_limit_date` | Assigned during processing, not at checkout. |
| Reviews | Written after delivery. |

## Alternatives considered

**Exclude payment entirely.** The payment record is a separate table and
`approved_at` is clearly after the fact, which suggests the whole payment is
too. Rejected because the method, instalment count and amount are all chosen at
checkout; only the approval is later. The distinction matters, and
`payment_type` is one of the more plausible predictors available — boleto in
Brazil is settled in person and takes days to clear, which plausibly delays
despatch.

**Include `status`.** It has no variance at the prediction point and any
non-trivial value is the outcome. Rejected as the most direct leakage available
in this dataset.

## Assumptions

Two things are assumed rather than established, and both are false in some real
cases.

**The estimated delivery date exists at creation.** It may in practice be
computed later, adjusted for current warehouse load or courier capacity. The
assumption is unavoidable: it is half the target, and without it there is no
lateness to predict.

**The seller is assigned at creation.** Where several sellers stock the same
product, assignment may follow. If it does, the seller-to-customer distance —
the most promising feature available — does not exist at the prediction point
either. The dataset offers no way to distinguish the two cases, so assignment
at creation is assumed.

Both assumptions favour the model. If either fails in production, the feature
that depends on it is unavailable and the model degrades in a way this dataset
cannot reveal.

## Consequences

- The feature layer takes its input from this list, not from the curated
  schema. A column being present in `curated` is not a licence to use it.
- The API contract follows: the request body carries what a caller could know
  when the order is placed, and nothing else.
- Any feature added later must be justified against this document.
