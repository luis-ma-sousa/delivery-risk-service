# 0015 — The request carries keys; the service enriches

**Status:** Accepted
**Date:** 2026-08-26

## Context

The prediction is made at order creation, before the order exists in any
database, so the request cannot be a lookup by `order_id`: there is nothing to
look up. The caller must send the order.

But the caller is a checkout system. It knows what was bought — product
identifiers, seller, price, freight, postcode, payment method — and it does not
hold the catalogue. Product weight and dimensions, and the coordinates of a
postcode prefix, are facts the service already stores.

## Decision

The request body carries identifiers and order-specific values. The service
resolves everything else from `curated`.

**Sent by the caller:** purchase timestamp, estimated delivery date, customer
postcode prefix, payment type, instalments and value, and one line per item
with `product_id`, `seller_id`, price and freight.

**Resolved by the service:** product category, weight and dimensions; seller
postcode prefix; and the coordinates of both postcode prefixes, from which the
distance is computed.

## Alternatives considered

**The caller sends everything, including product attributes.** Rejected: a
product's weight is a fact of the catalogue, not of the order. If the caller
asserts it, two callers can disagree about the same product and neither is
detectable. It would also require every caller to replicate the catalogue.

**The request carries only an `order_id`.** Rejected: at the prediction point
the order has not been written anywhere (ADR 0014), so there is no row to
read.

## Consequences

- The endpoint depends on the database. Its tests need one, or a substitute.
- A `product_id` or `seller_id` the catalogue does not contain is a bad
  request, not a server error, and the response should say which identifier
  failed.
- A postcode prefix absent from `zip_code_locations` is not an error: 278
  customers are in that position (ADR 0004). Distance is null and the model
  must accept it.
- The lookup sits in the critical path of every request, which is the
  materialised aggregation ADR 0003 was written for.
