# 0016 — Timestamps at the API boundary must carry an offset

**Status:** Accepted
**Date:** 2026-08-27

## Context

ADR 0002 settled how timestamps are stored: `timestamptz`, with the naive
values in the source CSVs read as local time in `America/Sao_Paulo`. That
assumption is sound for ingestion because the source is a fixed set of files
that cannot be asked what it meant.

The HTTP contract inherited naive timestamps without a decision of its own. A
request mixing one naive and one offset-bearing timestamp made the service
return 500: Python cannot compare an aware datetime with a naive one, and the
comparison sits inside a validator. A malformed request was being reported as
a server fault.

## Decision

`purchase_timestamp` and `estimated_delivery_date` must both carry a UTC
offset. A request without one is rejected with 422.

The offset need not be Brazilian. Two offset-bearing timestamps denote absolute
instants and compare correctly whatever zones they are expressed in.

## Alternatives considered

**Assume `America/Sao_Paulo` for naive values, as ingestion does.** Rejected on
two grounds. A caller in another timezone would have its timestamps silently
reinterpreted, and the resulting prediction would be wrong with nothing to
signal it. And in a mixed request, one field would be interpreted by us and the
other taken as given, which is harder to reason about than rejecting both.

**Accept naive values and compare them as naive.** Rejected: it defers the
problem to the feature layer, which has to reconcile them against
`timestamptz` columns anyway.

## Consequences

- The policy differs from ingestion, deliberately. Where there is someone to
  ask, the boundary demands; where there is not, it assumes and records the
  assumption.
- Callers must send an offset. This is a small cost to them and removes a class
  of error that is otherwise undetectable.
- The validator comparing the two timestamps can no longer raise, so a bad
  request is a 422 rather than a 500.
