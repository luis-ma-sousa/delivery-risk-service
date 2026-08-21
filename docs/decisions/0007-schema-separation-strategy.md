# 0007 — One database, two schemas

**Status:** Accepted
**Date:** 2026-08-21

## Context

ADR 0001 established two layers: `raw`, a faithful mirror of the CSVs, and
`curated`, constrained and analysis-ready. That decision says nothing about
how the two are physically separated. The options are two schemas inside one
Postgres database, or two separate databases.

## Decision

One database, two schemas: `raw` and `curated`.

## Alternatives considered

**Two separate databases.** Rejected on three grounds.

Transactions do not span databases. The transformation from `raw` to `curated`
reads from one and writes to the other, and as a single transaction it either
completes or leaves nothing behind. Across two databases there is no native way
to make that atomic, so a partially populated `curated` layer becomes possible
and reconciliation has to be hand-written.

Joins do not span databases either. Comparing row counts between layers,
verifying that an exclusion removed what it claimed, or inspecting rows that
failed to carry over are all routine queries across the boundary. Within one
database these are ordinary joins; across two they require foreign data
wrappers, which is disproportionate infrastructure for the problem.

Connection management doubles. The service in milestone 2 holds a connection
pool. Two databases mean two pools, two configured URLs and two failure modes,
where a schema is only a prefix on a table name.

**One schema, distinguished by table name prefixes.** Rejected: naming
conventions are not enforced, so nothing prevents a curated table from being
created without its prefix, and permissions cannot be granted per prefix.

## Consequences

- Isolation is preserved where it matters: schemas are separate namespaces with
  independent permissions. The application can be granted read access to
  `curated` and denied `raw` entirely.
- Postgres creates a `public` schema by default and places unqualified objects
  there. Alembic must be configured to target the intended schema explicitly,
  or migrations will create tables in the wrong place.
- Every table reference in application code and migrations is schema-qualified.
