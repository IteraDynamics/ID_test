# Latent Transition Geometry — Frozen Hypothesis Test — 2026-09-17

## Status
Observation-only research. No production, strategy, portfolio, runtime, threshold, order, NAV, exposure, execution, or Core-label change is authorized.

## Predecessor evidence
The latent-state trajectory study found that trajectory information was incremental for predicting whether Core would change label, while PCA4 point state remained the stronger representation for forward variance/downside. Descriptively, proximity to an alternate Core centroid strengthened as a Core transition approached.

This document freezes the next hypothesis before its results are observed.

## Primary hypothesis
A causal continuous latent-state trajectory contains information about the **destination and timing** of an upcoming Core regime transition, beyond the current Core label and beyond the latent state point alone.

## Frozen questions
1. Which observed Core source→destination transitions have adequate support to evaluate separately?
2. Does trajectory geometry discriminate the destination of the next Core transition?
3. Does predictive information strengthen as the transition approaches?
4. Does movement toward the eventual destination centroid precede the Core label flip?
5. Are effects supported across BTC/ETH, 1H/4H, and yearly walk-forward folds rather than being driven by one market/period?

## Frozen horizons
Evaluate 1, 2, 3, 5, 7, 10, and 14 calendar-day forward horizons. No horizon may be added or removed after results are inspected for the purpose of improving the conclusion.

## Representations
- Core label only
- PCA4 point state only
- trajectory geometry only
- Core + PCA4
- Core + trajectory
- PCA4 + trajectory
- Core + PCA4 + trajectory

Trajectory geometry is inherited unchanged from the predecessor study. No feature thresholds are tuned.

## Destination task
For each observation, identify the first future Core-label change within each frozen horizon. Its new Core label is the destination. Observations with no transition in the horizon are NO_TRANSITION.

Evaluate multiclass probabilistic prediction with training-only fitted models and Brier-style multiclass loss. Report class counts and refuse destination-specific interpretation where support is inadequate.

## Transition-pair geometry
For each sufficiently supported source→destination pair, report by lead day:
- distance to eventual destination centroid;
- distance to current/source centroid;
- destination-vs-source distance margin;
- change in destination distance;
- velocity alignment toward eventual destination centroid;
- speed and acceleration magnitude.

Centroids are fit only on pre-cutoff training observations.

## Support discipline
A source→destination pair is descriptive only unless it has at least 20 matured training events and at least 5 evaluation events in a fold. Aggregate reporting must expose the number of supported folds. Unsupported pairs remain in counts but cannot support a positive conclusion.

## Evaluation
- BTC and ETH
- 1H and 4H source inputs
- UTC-midnight snapshots, consistent with predecessor studies
- yearly 2020–2025 walk-forward folds
- all transforms/centroids/models fit on pre-cutoff matured training observations only
- deterministic/replay-safe execution
- fail closed on maturity or finite-data violations

## Decision rule
The hypothesis is supported only if trajectory-containing representations show stable out-of-sample incremental destination/timing information beyond Core and PCA4 comparators, and eventual-destination geometry shows a coherent approach pattern with adequate event support across multiple asset/timeframe/fold combinations.

A merely descriptive centroid relationship, isolated transition pair, or in-sample effect is insufficient.

## Guardrail
This test concerns state information only. It cannot authorize trading, return-alpha claims, risk sizing, exposure changes, or runtime integration.