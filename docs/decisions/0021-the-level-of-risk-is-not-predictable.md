# 0021 — The level of risk is not predictable from this data

**Status:** Accepted
**Date:** 2026-09-06

## Context

A logistic regression on nine structural features was scored on six monthly
windows, each trained on everything before it:

| window  | observed | predicted | brier   | baseline | auc   |
|---------|----------|-----------|---------|----------|-------|
| 2018-03 | 21.4%    | 8.6%      | 0.18061 | 0.18666  | 0.601 |
| 2018-04 | 5.3%     | 9.5%      | 0.04907 | 0.05179  | 0.756 |
| 2018-05 | 8.2%     | 9.5%      | 0.07269 | 0.07563  | 0.707 |
| 2018-06 | 1.4%     | 7.4%      | 0.01753 | 0.01892  | 0.729 |
| 2018-07 | 4.5%     | 11.3%     | 0.04734 | 0.04423  | 0.685 |
| 2018-08 | 10.4%    | 11.7%     | 0.09177 | 0.09371  | 0.683 |

Discrimination is real and stable: AUC between 0.68 and 0.76 in five of six
windows. Calibration is not. The predicted mean moves between 7.4% and 11.7%
while the observed rate moves between 1.4% and 21.4%, and the model beats the
constant baseline by 3% to 7% — in July it loses to it.

Two explanations were tested.

**System load.** Orders placed in the preceding 7 and 30 days were added as
features, on the hypothesis that congestion explains the bad months. It does
not: March 2018 saw 7098 orders in the preceding month with a 21.4% late rate,
August 2018 saw 7140 with 10.4%. Adding the features improved March and made
four of the other five windows worse, apparently by learning that later
periods have more orders and more delay — a relationship that does not survive
into the next month.

**Recalibration on recent outcomes.** Shifting predictions in log-odds space
to match a recently observed rate preserves ranking and corrects the level.
With a realistic thirty-day lag, the reference rate points the wrong way in
four of six windows. With no lag at all — knowledge nobody has, since those
orders are still in transit — the reference is simply the previous month's
rate, and that does not predict the next: 21.1% precedes 5.3%, 8.4% precedes
1.4%, 4.6% precedes 10.4%.

**A more expressive model.** Gradient boosting was run over the same windows
and the same feature matrix:

| window  | brier   | auc   | logistic brier | logistic auc |
|---------|---------|-------|----------------|--------------|
| 2018-03 | 0.17572 | 0.673 | 0.18061        | 0.601        |
| 2018-04 | 0.05123 | 0.711 | 0.04907        | 0.756        |
| 2018-05 | 0.07284 | 0.705 | 0.07269        | 0.707        |
| 2018-06 | 0.01748 | 0.681 | 0.01753        | 0.729        |
| 2018-07 | 0.05286 | 0.584 | 0.04734        | 0.685        |
| 2018-08 | 0.09381 | 0.606 | 0.09177        | 0.683        |

It is better in March, the hardest window, and worse in the last three, where
its AUC falls to 0.584 and 0.606 and its Brier score in August is worse than
the constant baseline. The degradation tracks training set size: the more
history it is given, the worse it does on the month that follows. That is what
overfitting to conditions which have since changed looks like. Logistic
regression, being unable to find those patterns, generalises better.

## Decision

The service predicts relative risk, not absolute probability. This is stated
rather than hidden, and no recalibration layer is added.

## Alternatives considered

**Add load features anyway.** Rejected on the measurement above: better in one
window, worse in four.

**Recalibrate on the previous month.** Rejected: the reference has no
predictive relationship with the target month, so the correction is as likely
to increase error as reduce it.

**Causal inference over the operational variables.** Rejected: it answers a
different question — what would happen if something were changed — and it
requires the causes to be observed. Whatever drives March 2018 is not in this
dataset.

**A more expressive model.** Rejected on the measurement above. Gradient
boosting does not fail because it is badly tuned; it fails because there is
recent structure to overfit and that structure does not persist. Capacity is
not the binding constraint.

## Consequences

- The predicted probability should be read as a ranking, not as a rate. An
  order at the ninetieth percentile of predicted risk really is riskier than
  one at the tenth; the number attached to it is not the chance it is late.
- Brier score is reported alongside the constant baseline, so that the small
  margin is visible rather than implied.
- A calibration layer becomes worth revisiting if a source of operational
  state — carrier capacity, strikes, holidays — is ever available. Nothing in
  the Olist dataset serves that purpose.
- This is a property of the problem as posed, not a failure of the model. A
  better model would rank slightly better and would not know the level either.
