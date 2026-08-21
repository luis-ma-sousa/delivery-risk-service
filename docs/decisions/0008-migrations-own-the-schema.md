# 0008 — Migrations own the database schema

**Status:** Accepted
**Date:** 2026-08-21

## Context

The database needs two schemas, `raw` and `curated`, before any table can be
created. Two mechanisms are available: a SQL script mounted into the Postgres
image's initialisation directory, or an Alembic migration.

## Decision

Alembic owns every structural change to the database, including the creation
of the schemas themselves. The Compose file provisions the server and nothing
more.

## Alternatives considered

**A SQL script in `/docker-entrypoint-initdb.d/`.** Rejected because those
scripts run only when the data volume is empty. A change to the script has no
effect on an existing database, so the only ways to apply one are to destroy
the volume and reload everything, or to apply the change by hand — leaving the
running database in a state the repository does not describe. Alembic applies
each change exactly once, in order, and records what has run.

**Splitting responsibility: schemas in Compose, tables in Alembic.** Rejected
because the structure of the database would then be described in two places
governed by different rules, and any discrepancy would require knowing which
tool was responsible for which part.

## Consequences

- Starting the database and preparing it are two separate steps. The task
  runner should offer a single target that does both.
- Schema creation is versioned and reversible like any other migration.
- Test databases are a distinct problem: Alembic requires an existing database
  to connect to, so creating one is outside its reach. An initialisation script
  remains the right tool there, and using it for that purpose does not
  contradict this decision.
