# 0003 — Aggregated geolocation table

**Status:** Accepted
**Date:** 2026-08-21

## Context

Customers and sellers are located by postcode prefix only; neither table
carries coordinates. The geolocation catalogue holds 1000163 geocoded points
across 19015 distinct prefixes — a median of 29 points per prefix, up to 1146.
Nothing links a specific point to a specific customer, so a prefix must be
collapsed to a single coordinate before any distance can be computed.

Measured properties of the catalogue:

- Latitude span within a prefix: median 0.0148 degrees (about 1.6 km),
  p75 0.0410 degrees, max 77.03 degrees.
- 235 prefixes (1.24%) span more than one degree of latitude.
- 47 points fall outside the Brazil bounding box, some on other continents.
- 157 customer prefixes and 7 seller prefixes are absent from the catalogue,
  affecting 0.28% and 0.23% of rows respectively.

## Decision

A materialised table in `curated`, keyed on `zip_code_prefix`, holding the
median latitude and longitude of each prefix, computed after discarding points
outside the Brazil bounding box.

Median rather than mean: the mean span is ten times the median and the standard
deviation thirteen times the mean, so the distribution is contaminated by
extreme outliers that a mean would propagate into the centroid.

## Alternatives considered

**Aggregate on the fly in each query.** Rejected: the API serves predictions
per request, and a `GROUP BY` over a million rows in the critical path of every
request is not acceptable. Materialised, the lookup is a primary key hit.

**Filter outliers within each prefix before aggregating.** Rejected as
redundant: the median already resists outliers that are a minority within a
prefix, and the alternative introduces an arbitrary distance threshold for no
measured gain.

**Use a true polygon of Brazil rather than a bounding box.** Rejected: the
errors observed are thousands of kilometres out, not marginal. Filter precision
should match error magnitude, and a polygon adds a geometry dependency to catch
possibly one or two additional rows.

## Consequences

- 235 prefixes yield a coordinate that represents no real location. Distances
  computed from them are unreliable. At 1.24% this is accepted and recorded
  rather than corrected.
- The foreign key from customer and seller prefixes to this table is nullable,
  per ADR 0004. Distance is null for 0.28% of customers.
- Postcode prefixes are stored as text, never as integers. Prefixes in the
  01000–09999 range carry a leading zero that integer parsing silently
  discards, which would break the join for the entire São Paulo region.
- Five prefixes have every point outside the bounding box and therefore do not
  survive aggregation at all. One of them is used by a customer, so the count
  of customers without a location is 279 rather than the 278 the source would
  suggest.
