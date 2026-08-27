# 0017 — The request carries a list of payments

**Status:** Accepted
**Date:** 2026-08-27

## Context

The contract initially carried a single payment: type, instalments and value.
The source data does not support that shape. 2961 of 99440 orders with a
payment record carry more than one — 3.0%. Most of those carry exactly two, but
the distribution has a long tail, up to 29 payments on a single order.

Inspecting the multiple-payment orders shows what they are. Vouchers account
for 4581 of the lines against 2823 for credit cards and 3 for debit cards, and
no boletos at all. The order with 29 payments is 29 vouchers, ranging from
R$0.32 to R$150.00. The pattern is accumulated credit covering part of a total,
with a card settling the rest — not an instalment plan.

Measured against the target, it shows little marginal association with
lateness: orders with multiple payments are late 7.3% of the time against 8.1% for the rest, a difference of under a percentage point on 2874 orders. Redeeming vouchers is instantaneous and touches no part of the logistics chain, so this is what one would expect.

## Decision

`payments` is a list with at least one entry. Each entry carries its type,
instalment count and value.

## Alternatives considered

**Keep one payment, defined as the largest by value.** Rejected. The absence of
a marginal correlation is not a reason to discard the data at the contract
boundary: the contract records what the caller knows, and the feature layer
decides what to use. Interactions with other variables cannot be tested against
information that was thrown away before it arrived.

**Keep one payment and add derived fields, such as a voucher count.** Rejected:
it puts a feature decision in the contract, and any further derivation would
require a contract change.

## Assumptions

The checkout system holds the payments individually when it calls. The
sequential numbering in the source — 1 through 29, with distinct values —
indicates lines that exist at checkout rather than an aggregation performed
later, but this is inferred from the data rather than established.

## Consequences

- A caller with a single payment sends a list of one.
- Fields inside `PaymentLine` drop the `payment_` prefix, per ADR 0011.
- The feature layer can derive payment count, distinct methods, voucher share
  and total value without a contract change.
