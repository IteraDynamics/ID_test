# Continuous Core Regime Stability — Frozen Hypothesis Test — 2026-09-17

## Status
Observation-only research. No production, strategy, portfolio, runtime, threshold, order, NAV, exposure, execution, or Core-label change is authorized.

## Motivation
Prior observation-only work found: (1) PCA4 continuous state materially improves risk characterization over Core labels; (2) trajectory information improves short-horizon detection that Core will change label; (3) trajectory adds little robust information about the destination once Core and PCA4 are known. The defensible next question is therefore whether current Core-label stability itself can be quantified continuously.

## Primary hypothesis
Within a fixed current Core label, a causal continuous score can distinguish observations in a deeply established/stable state from observations whose current Core classification is becoming unstable and approaching any label transition.

## Frozen target
For each observation and horizon H, `transition_within_H = 1` iff the first future Core label differing from the current label occurs within H calendar days. Incomplete forward windows are missing, never negative.

Frozen horizons: 1, 2, 3, 5, 7, 10, 14 days.

## Frozen candidate information
All continuous information is inherited without tuning from predecessor studies and fit causally on training data only:
- PCA4 point state;
- trajectory geometry: speed, acceleration magnitude, training-center distance, radial velocity/alignment, current-Core centroid distance, nearest-alternate centroid distance, centroid margin, margin velocity;
- Core episode age: consecutive sampled days already spent in the current Core label.

No destination identity is used.

## Comparators
- unconditional constant transition probability;
- Core label only;
- episode age only;
- PCA4 only;
- trajectory only;
- Core + episode age;
- Core + PCA4;
- Core + trajectory;
- Core + PCA4 + trajectory;
- Core + PCA4 + trajectory + episode age.

## Continuous stability score
The fitted out-of-sample probability of `transition_within_H` is the instability probability. Stability is `1 - p_transition`. This is a research score only; no threshold or stable/unstable cutoff will be selected in this study.

## Evaluation
- BTC and ETH;
- 1H and 4H source inputs;
- UTC-midnight sampled panels;
- yearly 2020–2025 walk-forward evaluation;
- training-only transforms/models;
- deterministic logistic regression with fixed regularization inherited from predecessor work;
- Brier score and skill versus constant and Core-only comparators;
- AUC reported as descriptive discrimination only where both classes exist;
- calibration by fixed probability deciles, with no post-hoc recalibration;
- per-current-Core-label event rates and discrimination;
- monotonicity: observed transition frequency across predicted-instability deciles;
- score lead profile before actual Core transitions at 1,2,3,5,7,10,14 days.

## Advance rule
The hypothesis is supported only if a continuous representation adds stable out-of-sample Brier skill beyond Core alone, with positive incremental skill across a substantial majority of the 24 asset/timeframe/year folds at short/intermediate horizons, and if higher predicted instability corresponds to materially higher realized transition frequency without dependence on one asset/timeframe or one Core label.

AUC alone, isolated labels, or a visually attractive lead curve is insufficient.

## Guardrail
This study does not authorize a production confidence field, transition threshold, strategy filter, sizing rule, or execution change. Any such use requires a separately frozen downstream hypothesis and explicit authorization.