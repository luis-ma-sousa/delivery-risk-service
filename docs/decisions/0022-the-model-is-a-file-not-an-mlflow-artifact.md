# 0022 — The served model is a file, not an MLflow artifact

**Status:** Accepted
**Date:** 2026-09-06

## Context

MLflow tracks the experiments in `scripts/train.py`, where six monthly cutoffs
are compared across two model families. That is what it is good at.

Serving the model from MLflow was attempted and does not work. Its local
tracking store records absolute artifact paths: a run registered on this
machine points at `/Users/louis/Desktop/.../mlruns/2/models/...`, and the
container loading it fails with `No such artifact: 'MLmodel'`. Making it work
would mean mounting the host path inside the container under its own name,
which puts one developer's home directory in `docker-compose.yml` and stops
anyone else running the project.

Recent MLflow versions also refuse a plain filesystem backend outright, on the
grounds that it is in maintenance mode.

## Decision

The served model is written to `models/` as a joblib file with a JSON sidecar
holding the column order, the imputation medians and the date through which it
was trained. The service reads that directory, and the container mounts it.

MLflow keeps the experiment tracking.

## Alternatives considered

**Mount the MLflow store, replicating the host path.** Rejected: the compose
file would contain an absolute path belonging to one machine.

**Run an MLflow tracking server with shared artifact storage.** This is the
production answer, and it is what makes MLflow work for serving. Rejected as
infrastructure this project does not otherwise need — a server, a database and
a bucket to serve one model from one container.

**Bake the model into the image.** Rejected: the image would need rebuilding
on every retrain, and the model is not source code.

## Consequences

- `models/` is gitignored. The model is regenerable from the data and the
  code; a binary in the repository is not.
- The column order travels with the model. Scikit-learn matches features by
  position, so a model loaded by code that computes features in a different
  order would answer confidently and wrongly.
- The version string is the date the model was trained through, which tells a
  consumer how stale it is. Given how much the late rate moves month to month
  (ADR 0021), that is worth surfacing.
- Deploying a new model means writing the directory and restarting the
  service. There is no hot reload and no model registry.
