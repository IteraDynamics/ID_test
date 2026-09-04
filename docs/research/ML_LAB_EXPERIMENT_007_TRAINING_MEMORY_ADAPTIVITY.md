# ML Lab Experiment 007 — Cross-Sectional Training-Memory Adaptivity

## Status

**EXPLORATORY / NON-CONFIRMATORY**

This experiment is confined to the isolated ML Lab. It does not authorize any Core, runtime, strategy, threshold, order, NAV, exposure, portfolio, paper-trading, live-trading, or capital change.

The reserved Campaign #50 2025 holdout remains untouched.

## Motivation

Experiment 005 produced the first credible nonlinear advantage in the ML Lab: GBM beat Ridge across the 2012–2021 cross-sectional ETF ranking interval, but the advantage reversed in 2022–2024.

Experiment 006 diagnosed three descriptive mechanisms:

- relationship shift,
- model brittleness,
- asset concentration.

The most important finding was that several volatility-state relationships weakened or changed sign after 2021 while the expanding GBM remained highly dependent on those variables.

That diagnosis justifies a bounded test of training-memory adaptivity.

## Question

Does reducing training memory improve post-2021 adaptation of the unchanged nonlinear model without destroying its earlier predictive structure?

## What is fixed

Experiment 007 preserves Experiment 005 exactly with respect to:

- universe,
- source files,
- 2024-12-31 cutoff,
- weekly anchor cadence,
- 20-session target horizon,
- target definition,
- feature set,
- cross-sectional percentile-rank transformation,
- Ridge specification,
- GBM specification,
- random seed,
- annual expanding test folds,
- target-horizon embargo,
- evaluation metrics.

No model-family, target, feature, or hyperparameter search is allowed.

## Universe

The unchanged 14-ETF cross-section is:

- RSP
- MDY
- IWM
- IWD
- IWF
- XLB
- XLE
- XLF
- XLI
- XLK
- XLP
- XLU
- XLV
- XLY

## Target

At each weekly anchor, rank the 14 assets by:

`forward 20-session return / (trailing 60-session realized volatility * sqrt(20))`

The model target is the within-anchor percentile rank of that quantity.

## Features

The unchanged 12 cross-sectional percentile-rank features are:

1. `ret_5d_xrank`
2. `ret_20d_xrank`
3. `ret_60d_xrank`
4. `ret_120d_xrank`
5. `vol_20d_xrank`
6. `vol_60d_xrank`
7. `vol_ratio_20_60_xrank`
8. `distance_sma_20_xrank`
9. `distance_sma_120_xrank`
10. `drawdown_120_xrank`
11. `range_position_120_xrank`
12. `volume_z_60_xrank`

## Models

Unchanged from Experiment 005:

### Ridge

`StandardScaler + Ridge(alpha=10.0)`

### GBM

`GradientBoostingRegressor(n_estimators=200, max_depth=2, learning_rate=0.04, random_state=42)`

### Naive reference

Cross-sectional trailing 60-session return rank.

The naive reference is reported once because it does not depend on training memory.

## Training-memory schemes

Exactly three schemes are compared.

### Expanding

All eligible prior data whose target end date is strictly before the first test anchor of the year.

This reproduces Experiment 005.

### Trailing 5 years

Same embargo condition, but training anchors must also be no earlier than five calendar years before the first test anchor.

### Trailing 3 years

Same embargo condition, but training anchors must also be no earlier than three calendar years before the first test anchor.

No other windows are allowed in this experiment.

## Evaluation

Annual OOS folds remain 2012–2024 where support is sufficient.

Primary metric:

- mean cross-sectional Spearman rank IC by anchor.

Secondary metrics:

- median rank IC,
- positive-IC fraction,
- mean top-quartile minus bottom-quartile raw target spread,
- yearly mean rank IC,
- GBM minus corresponding Ridge IC within each memory scheme.

The report separately summarizes:

- 2012–2021,
- 2022–2024,
- full eligible OOS interval.

## Interpretation discipline

This experiment is not a historical window-selection exercise.

The central diagnostic question is whether shorter memory produces a coherent pattern consistent with adaptation:

1. materially better 2022–2024 GBM performance than expanding GBM,
2. preferably positive GBM-minus-Ridge post-2021,
3. without complete destruction of the pre-2022 GBM signal.

Because the 3-year and 5-year windows are motivated by Experiment 006, any apparent advantage is exploratory and discovery-contaminated.

A winning window may not be promoted, deployed, or interpreted as a production setting from this experiment.

## Explicit non-actions

Experiment 007 does not authorize:

- selecting a production training window,
- changing Core,
- changing any runtime or portfolio behavior,
- using the reserved 2025 holdout,
- hyperparameter tuning,
- feature selection,
- target changes,
- additional window search,
- portfolio mapping.
