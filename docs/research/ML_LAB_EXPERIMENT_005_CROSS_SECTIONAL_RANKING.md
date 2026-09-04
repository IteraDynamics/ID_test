# ML Lab Experiment 005 — Cross-Sectional ETF Ranking

**Branch:** `agent/ml-lab-exploration-20260903`

**Status:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

**Parent boundary:** `docs/research/ML_LAB_EXPLORATION_CHARTER.md`

## Question

Can a shallow nonlinear model rank a heterogeneous cross-section of liquid U.S. equity/style/sector ETFs by next-month risk-adjusted return better than a simple linear ranker and a naive momentum rank, using only information available at the ranking timestamp?

This is not a strategy or portfolio-construction test. It does not assign weights, simulate trading, or alter any Itera runtime behavior.

## Why this experiment

ML Lab Experiments 001–004 found genuine predictive structure in BTC/ETH price state but no durable incremental value from shallow GBM over logistic regression. Those were low-dimensional single-series problems.

Cross-sectional ranking is structurally different:

- each timestamp contains multiple contemporaneous entities;
- the prediction target is relative rather than absolute;
- assets differ in sector/style/state;
- nonlinear interactions may matter across heterogeneous entities even when they do not in a single time series.

The repository already contains a clean 14-member breadth ETF universe from Campaign #50. Experiment 005 reuses those source files but does **not** consume Campaign #50's reserved 2025 confirmation holdout.

## Universe

Exactly 14 ETFs:

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

Expected files: `data/<TICKER>_1D.csv`.

All assets are intersected to a common daily session calendar.

## Temporal boundary

- source history may begin in 2005;
- latest allowed source/target date: **2024-12-31**;
- Campaign #50's 2025 holdout is not read into any feature or outcome;
- annual OOS test folds begin in **2012**.

## Anchors

Use every fifth common trading session after enough history exists for the 120-session features.

This produces approximately weekly cross-sectional observations and reduces target overlap relative to daily anchors.

## Target

For each asset at anchor `t`:

1. forward return = close at `t+20 common sessions` / close at `t` - 1;
2. risk scale = trailing 60-session standard deviation of daily log returns at `t` times `sqrt(20)`;
3. raw target = forward return / risk scale;
4. within each anchor date, convert the 14 raw targets to cross-sectional percentile ranks in `[0,1]`.

The model predicts the **cross-sectional target rank**.

The target-end date is retained explicitly. For each annual test fold, training rows are permitted only when their 20-session target-end date is strictly before the first test-year session. This prevents a training label from reaching into the test period.

## Features

Twelve causal state variables are computed per asset and then converted to same-date cross-sectional percentile ranks:

1. 5-session return
2. 20-session return
3. 60-session return
4. 120-session return
5. 20-session realized volatility
6. 60-session realized volatility
7. 20/60 volatility ratio
8. distance from 20-session SMA
9. distance from 120-session SMA
10. drawdown from 120-session high
11. position inside the 120-session high-low range
12. 60-session volume z-score

Using same-date cross-sectional ranks makes features comparable across heterogeneous ETFs without using future information.

## Models

### Naive momentum

Score = cross-sectional percentile rank of trailing 60-session return.

No fitting.

### Ridge

`StandardScaler + Ridge(alpha=10.0)`

This is the simple linear benchmark.

### Shallow GBM

`GradientBoostingRegressor(n_estimators=200, max_depth=2, learning_rate=0.04, random_state=42)`

No hyperparameter search.

## Chronological evaluation

Expanding annual folds, test years 2012 through 2024 when data support exists.

For each year:

1. train Ridge and GBM only on earlier eligible anchors whose target windows finish before the test-year start;
2. predict every asset at every eligible weekly anchor in the test year;
3. at each anchor, rank model scores cross-sectionally;
4. compare predicted ranks with realized target ranks.

## Metrics

Primary exploratory metrics:

- per-anchor Spearman rank IC between predicted score and realized target rank;
- mean and median IC;
- fraction of anchors with positive IC;
- yearly mean IC;
- top-quartile minus bottom-quartile realized raw target spread based on predicted ranking.

Also report the same metrics for the naive 60d momentum ranking.

The key comparison is GBM versus Ridge. A useful nonlinear result would require more than a single pooled numerical edge: GBM should improve mean/median rank IC across multiple years without depending on one sector or one year.

## Interpretability

Report:

- average absolute Ridge coefficients;
- average GBM feature importance;
- per-year GBM-minus-Ridge mean IC;
- per-asset contribution diagnostics to identify whether apparent lift is concentrated in one ETF.

## Interpretation discipline

This entire branch is exploratory. The 2012–2024 interval is discovery-contaminated after this run.

No result is confirmatory evidence, and no result authorizes Core v1/Core v2/runtime/threshold/order/NAV/exposure/paper/live/capital action.
