# 0019 — Temporal split, and the period worth training on

**Status:** Accepted
**Date:** 2026-09-06

## Context

The late-delivery rate is not stable over this dataset. By month of purchase
it ranges from 1.4% in June 2018 to 21.4% in March 2018, with 14.3% in
November 2017 — Black Friday, where volume rises from 4478 to 7288 orders and
the rate triples.

None of the eleven features knows what month it is. That variance is driven by
operating conditions the model cannot see, which makes how the data is split a
question with real consequences rather than a formality.

The period is also uneven at both ends. September to December 2016 hold 263
orders across four months, two of which contain a single order each. September
and October 2018 are absent entirely: orders placed then had not been delivered
when the dataset was extracted, so they fail the `delivered_customer_date IS
NOT NULL` filter. What survives near the end is biased toward fast deliveries.

## Decision

Splits are temporal. Everything before a cutoff is training; a bounded window
after it is testing. No order in the test set precedes an order in the
training set.

The usable period is 2017-01-01 to 2018-09-01, in `America/Sao_Paulo`.

Test windows are given as explicit start and end dates rather than a number of
months. Months are uneven, and the question being asked — how does the model
do over these particular weeks — is clearer stated than inferred.

## Alternatives considered

**Random split.** Rejected. Orders from the same week would appear in training
and test, so the model would learn the rate prevailing in the period it is
being scored on. That is information it cannot have when predicting an order
placed today, and the resulting performance would be an artefact.

**A single cutoff with an open-ended test set.** Rejected: averaging over a
period in which the rate moves by a factor of fifteen hides both the good
months and the bad ones. Reading performance window by window shows whether
the model degrades as it ages, which is the question worth answering.

**Keeping the 2016 months.** Rejected for 0.3% of the data and a month with a
single order in it.

**Keeping September and October 2018.** Rejected: the orders that survive
right censoring are the ones that were delivered quickly, so the observed rate
there is not the rate.

## Consequences

- Training on data up to June 2018 means training at 8.8% and testing at 1.4%.
  Poor calibration on that window is expected and is a property of the
  problem, not a fault of the model.
- Discrimination and calibration must be read separately. A model may rank
  orders correctly while being wrong about the level.
- 96184 orders are usable, of the 96447 that are trainable.
