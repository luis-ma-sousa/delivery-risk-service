# 0020 — Missing values are imputed and flagged

**Status:** Accepted
**Date:** 2026-09-06

## Context

Three features are null for some orders. Distance is null for 481 of 96447
trainable orders, where the customer's postcode prefix has no coordinates or a
seller's does not (ADR 0004). Weight and volume are null for the handful of
orders containing a product with no recorded dimensions.

Logistic regression does not accept missing values. Gradient boosting does,
but choosing a model to avoid a decision is not the same as making it.

## Decision

Missing numeric values are filled with the median of the training set, and
each imputed column is accompanied by a binary indicator recording that the
value was absent.

Medians are computed on the training set alone and applied unchanged to the
test set.

The two categorical features, customer state and origin state, are excluded
from the baseline. They carry 27 values each, and 54 one-hot columns alongside
nine numeric features would make the baseline mostly a model of geography.
They are added afterwards, when there is a number to compare against.

## Alternatives considered

**Impute without an indicator.** Rejected: a missing distance is not a median
distance. Filling it silently tells the model the order was average, when what
is true is that we do not know. The indicator lets "unknown" be its own
condition.

**Drop the rows.** Rejected: 481 orders is little, but the reason they are
missing is not random — they are concentrated in postcode prefixes the
geolocation catalogue does not cover, which is itself a property of where the
customer lives.

**Compute medians over the full dataset.** Rejected as leakage. The median of
the test period is not known when the model is trained.

**Use only models that accept nulls natively.** Rejected: it forecloses
logistic regression, which is the baseline this project wants, and it hides
the decision inside a library rather than stating it.

## Consequences

- The feature matrix has twelve columns: nine numeric and three indicators.
- Training and test matrices are built by the same function, in the same
  column order. Scikit-learn matches by position, not by name.
- If an indicator turns out to carry signal, that is worth reporting: it would
  mean orders we cannot locate behave differently from orders we can.
