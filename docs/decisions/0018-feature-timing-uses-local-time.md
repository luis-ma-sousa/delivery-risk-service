# 0018 — Timing features are derived in local operational time

**Status:** Accepted
**Date:** 2026-08-28

## Context

ADR 0016 requires requests to carry a UTC offset, which fixes the instant
unambiguously. It does not say which timezone the service should use when
deriving features from that instant.

Day of week and hour of purchase were initially read straight off the
timestamp as received. That makes them depend on the offset the caller chose:
the same moment sent as 14:30-03:00 and as 17:30Z produced hour 14 and hour 17,
and near midnight it would produce different days.

## Decision

Timing features are derived after converting to `America/Sao_Paulo`.

## Alternatives considered

**Derive in UTC.** Unambiguous and simple, but shifts every Brazilian order
three hours forward, so "placed in the evening" becomes "placed at night" and
the pattern the feature aims to capture is displaced rather than removed.

**Derive in the caller's offset, as received.** Rejected: the same instant
would produce different features depending on where the request came from,
which is not a property a feature may have.

## Consequences

- The relevant clock is the one the logistics operation runs on, which is the
  same frame ADR 0002 uses for stored timestamps.
- A test asserts that two offsets denoting the same instant produce identical
  timing features.
- Day of week and hour remain cyclical: hour 23 and hour 0 are adjacent in
  reality and distant numerically. Whether that needs a cyclical encoding is a
  modelling question, not a contract one.
