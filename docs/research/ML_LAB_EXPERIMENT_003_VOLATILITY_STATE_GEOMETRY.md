# ML Lab Experiment 003 — Volatility-State Geometry and Tail Severity Surface

**Branch:** `agent/ml-lab-exploration-20260903`

**Status:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

**Parent boundary:** `docs/research/ML_LAB_EXPLORATION_CHARTER.md`

## Questions

Experiment 003 has two linked exploratory questions.

### Part A — State geometry

What is the empirical relationship between current short-vs-long volatility state and the probability of a future 24-hour volatility expansion?

Specifically, does the strong predictability observed in Experiment 002 reduce to a simple monotonic/threshold relationship in:

- `vol_ratio_24_168`;
- current `realized_vol_24h`;
- `range_position_168h`;
- interactions among those variables?

### Part B — Tail severity surface

Does shallow nonlinear GBM become more useful relative to logistic regression as the volatility-expansion event becomes more severe and rarer?

The full fixed exploratory severity surface is:

- 1.25x
- 1.50x
- 1.75x
- 2.00x

where the event is `future_realized_vol_24h / trailing_realized_vol_24h >= threshold`.

No threshold is designated primary and no threshold will be selected as a trading rule from these results.

## Data

- BTC hourly primary data, 2018-2025.
- ETH hourly locked transfer data, 2018-2025.

Expected local files:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`

No governed campaign holdout is consumed.

## Common feature vector

Reuse Experiment 002's 12 causal features unchanged:

1. `ret_1h`
2. `ret_24h`
3. `ret_72h`
4. `ret_168h`
5. `abs_ret_24h`
6. `realized_vol_24h`
7. `realized_vol_72h`
8. `realized_vol_168h`
9. `vol_ratio_24_168`
10. `vol_ratio_72_168`
11. `drawdown_from_high_168h`
12. `range_position_168h`

## Part A diagnostics

Using post-2020 rows as an explicitly exploratory descriptive sample, report separately for BTC and ETH:

1. Event rate by decile of `vol_ratio_24_168` for each severity threshold.
2. Event rate by decile of `realized_vol_24h` for each severity threshold.
3. Event rate by decile of `range_position_168h` for each severity threshold.
4. Two-dimensional 5x5 conditional tables for the 1.25x target:
   - `vol_ratio_24_168` quintile x `realized_vol_24h` quintile;
   - `vol_ratio_24_168` quintile x `range_position_168h` quintile.

Also report row counts in every cell so sparse regions are obvious.

These are descriptive diagnostics, not significance tests.

## Part B models

For every severity threshold, use exactly the same model forms:

### Naive

Constant probability equal to the BTC training event rate.

### Logistic

- `StandardScaler()`;
- `LogisticRegression(C=0.25, max_iter=2000, random_state=42)`;
- unweighted.

### Shallow GBM

- `GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.04, random_state=42)`.

No hyperparameter tuning.

## Chronological evaluation

Expanding annual walk-forward beginning with test year 2020.

For each threshold and each test year:

1. fit models on BTC rows strictly before that year;
2. evaluate on BTC rows in that year;
3. apply the exact fitted BTC estimators unchanged to ETH rows in the same year.

Minimum BTC training support for a threshold/year:

- 5,000 rows;
- at least 100 events;
- at least 100 non-events.

If a severe threshold lacks enough support for an early fold, skip that fold and report the support limitation rather than changing the threshold.

## Metrics

For every threshold, role, model, and year:

- ROC AUC;
- average precision;
- Brier score;
- top-5% event lift;
- top-1% event lift;
- event count/rate.

Also report:

- pooled OOS metrics;
- GBM-minus-logistic AUC delta by year;
- GBM-minus-logistic AP delta by year;
- number of eligible folds at each threshold;
- mean and median deltas across folds.

## Interpretation

The objective is not to identify the threshold with the highest backtest metric.

We are testing whether a pattern emerges across severity:

- if logistic remains equal or superior throughout, nonlinear complexity is not earning itself for this volatility-state representation;
- if GBM advantage increases coherently as events become rarer, especially on locked ETH transfer and top-tail metrics, that would motivate direct interrogation of a tail-specific nonlinear interaction;
- if apparent GBM advantage appears only at one threshold or one year, treat it as exploratory noise until a simpler structural explanation emerges.

Part A should help distinguish whether any ML signal is really just a simple threshold/monotonic relationship that can be expressed directly.

## Hard boundary

Experiment 003 is exploratory and contaminated by prior observation. No output authorizes Core v1/Core v2 composition, runtime, thresholds, orders, NAV, exposure, paper/live trading, execution, or capital action.