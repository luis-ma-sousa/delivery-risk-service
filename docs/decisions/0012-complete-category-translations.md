# 0012 — Category translations are completed in curated

**Status:** Accepted
**Date:** 2026-08-22

## Context

Products carry 73 distinct category names. The source translation file covers
71 of them. Two are absent: `pc_gamer` and
`portateis_cozinha_e_preparadores_de_alimentos`, together accounting for 13
products.

A foreign key from `products.category_name` to the translation table cannot be
declared while those two categories have no row to point at.

## Decision

The two missing translations are added during the transformation from `raw`
into `curated`:

- `pc_gamer` maps to `pc_gamer`
- `portateis_cozinha_e_preparadores_de_alimentos` maps to
  `kitchen_portables_and_food_preparers`

With the table complete, the foreign key is declared. It remains nullable:
610 products carry no category at all, which is a different condition from
carrying an untranslated one.

## Alternatives considered

**Leave `category_name` as free text with no foreign key.** Rejected: the
database would guarantee nothing about category values, and a typo in the
transformation would pass silently.

**Declare the foreign key and let the two categories resolve to null.**
Rejected: it would discard a known category from 13 products in order to
satisfy a constraint, which inverts the purpose of the constraint.

**Add the translations to the source CSV.** Rejected: `raw` mirrors the source
exactly (ADR 0009). The source has 71 translations and `raw` must say so.

## Consequences

- Two rows of `curated.category_translation` have no counterpart in `raw`.
  The delta between layers is no longer only subtractive.
- The English names for those two categories are our own, not Olist's. They
  are recorded here so the origin is traceable.
