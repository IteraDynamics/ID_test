# ML Lab Experiment 004 — Volatility Target Integrity Probe

**Branch:** `agent/ml-lab-exploration-20260903`

**Status:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

**Parent boundary:** `docs/research/ML_LAB_EXPLORATION_CHARTER.md`

## Question

Does current market state predict genuinely high future 24-hour realized volatility when the outcome is benchmarked against a slower historical volatility baseline known at time `t`, rather than against current 24-hour volatility itself?

This experiment exists to test whether the strong predictability in Experiments 002–003 survives removal of the target-definition confound created by using trailing 24h volatility in the denominator.

## Data

Primary asset: BTC hourly OHLCV.

Transfer asset: ETH hourly OHLCV.

Expected local files:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`

## Target family

Future 24h realized volatility is computed from returns strictly after `t`, from `t+1` through `t+24`.

The denominator is trailing **168h realized volatility**, known at time `t`.

Fixed exploratory severity surface:

- `future_vol_24h / trailing_vol_168h >= 1.00`
- `>= 1.25`
- `>= 1.50`
- `>= 1.75`

These thresholds form a descriptive severity map. No single threshold is selected as a winner or trading threshold.

## Why 168h baseline

A 168h realized-volatility baseline is deliberately slower than the 24h future outcome and is already part of the inherited feature set. It removes the direct current-24h-vol denominator overlap while preserving a causal reference scale.

Current 24h realized volatility remains allowed as a predictor. That is now legitimate because it no longer directly defines the label threshold.

## Features

Same compact causal feature vector used in Experiments 002–003:

1. 1h return
2. 24h return
3. 72h return
4. 168h return
5. absolute 24h return
6. trailing 24h realized volatility
7. trailing 72h realized volatility
8. trailing 168h realized volatility
9. 24h / 168h volatility ratio
10. 72h / 168h volatility ratio
11. drawdown from 168h rolling high
12. position inside the 168h high-low range

## Models

### Naive

Constant probability equal to BTC training event rate.

### Logistic

`StandardScaler + LogisticRegression(C=0.25, max_iter=2000, random_state=42)`

No class weighting.

### Shallow GBM

`GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.04, random_state=42)`

No tuning.

## Chronological evaluation

Expanding annual walk-forward beginning with test year 2020.

For each threshold and year:

1. fit on BTC observations strictly before that year;
2. evaluate on BTC observations in that year;
3. apply the exact fitted BTC model unchanged to ETH observations in that year.

## Metrics

For each threshold, model, role, and year:

- ROC AUC
- average precision
- Brier score
- top-5% lift
- top-1% lift
- event count/rate

Also report:

- pooled OOS metrics;
- yearly GBM-minus-logistic AUC and AP deltas;
- feature importance by fold;
- decile tables for `vol_ratio_24_168` against each target threshold.

## Interpretation

If strong predictability survives with the slower 168h denominator, then Experiments 002–003 were not merely artifacts of using current 24h volatility in the label denominator. The market-state structure is more substantive.

If AUC/AP collapse materially, then much of the prior apparent predictability was target construction plus mean reversion rather than independent forward-volatility forecasting.

If logistic still matches or beats GBM, nonlinear complexity remains unjustified for this feature set even if the target itself is genuinely predictable.

## Boundary

This is exploratory only. No threshold, model, or signal is authorized for portfolio/runtime/paper/live/capital use.