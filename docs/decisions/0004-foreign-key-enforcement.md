# 0004 — Directional foreign key enforcement

**Status:** Accepted
**Date:** 2026-08-19

## Context

Referential integrity in the Olist dataset is not uniform. Some parent-child
relationships hold completely; others have orphans on one side only. A single
blanket policy would either fail on load or enforce nothing.

## Decision

Foreign keys are decided per relationship, in the `curated` layer only, based
on measured orphan counts. The `raw` layer carries no foreign keys at all.

The foreign key from customer and seller postcode prefixes to the aggregated
geolocation table is nullable and not enforced: prefixes absent from the
geolocation source are expected, and a missing coordinate must not prevent a
customer or seller from existing.

## Alternatives considered

**Enforce every plausible foreign key.** Rejected: guarantees load failure on
relationships with known orphans, for no analytical gain.

**Enforce none, validate in application code.** Rejected: the point of using
Postgres over SQLite was constraints that actually fail. Declining to use them
discards that.

## Consequences

- Distance is null wherever a postcode prefix has no coordinates. Handling
  that null is a modelling decision, deferred to the feature layer.
- Load order matters in `curated`: parents before children.
- Each enforced key is traceable to an orphan count in the reconnaissance
  output.