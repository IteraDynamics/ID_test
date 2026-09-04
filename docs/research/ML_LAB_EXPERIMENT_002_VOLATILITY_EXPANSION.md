# ML Lab Experiment 002 — Volatility Expansion Nonlinearity Probe

**Branch:** `agent/ml-lab-exploration-20260903`

**Status:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

**Parent boundary:** `docs/research/ML_LAB_EXPLORATION_CHARTER.md`

## Question

Can a deliberately shallow nonlinear model predict a near-term volatility expansion state materially better than a competent simple logistic model, and does any lift transfer from BTC to ETH without retuning?

This is not a trading-strategy test. It does not evaluate direction, Sharpe, sizing, Core v1 changes, or production readiness.

## Why this experiment

Experiment 001 found that continuation ranking was learnable but that shallow GBM added little over logistic regression. Its feature importance nevertheless concentrated heavily on volatility state. Prior Jump Risk work also showed that discontinuous-risk states can be predictively learnable. Volatility expansion is therefore a more naturally nonlinear target than continuation direction and is a useful second probe of whether ML complexity can earn itself.

## Data

Primary asset: BTC hourly OHLCV.

Transfer asset: ETH hourly OHLCV.

Expected local files:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`

No governed campaign holdout is consumed.

## Target

Single 24-hour target.

At time `t`:

1. compute trailing 24-hour realized volatility from hourly log returns;
2. compute **future** 24-hour realized volatility using log returns strictly after `t`, from `t+1` through `t+24`;
3. define the expansion ratio as `future_vol_24h / trailing_vol_24h`;
4. label `volatility_expansion = 1` when the expansion ratio is at least **1.25**, otherwise 0.

The 1.25 threshold is fixed for this exploratory experiment and is not optimized.

## Feature vector

Twelve causal features, all available at or before `t`:

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

No regime, funding, volume, calendar, or external variables are included.

## Models

### Naive

Constant probability equal to the BTC training event rate.

### Logistic baseline

- standard scaling fit on BTC training data only;
- `LogisticRegression(C=0.25, max_iter=2000, random_state=42)`;
- **no class weighting**, so probability calibration and Brier score are directly interpretable.

### Shallow GBM

- `GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.04, random_state=42)`.

No hyperparameter search.

## Chronological evaluation

Expanding annual walk-forward beginning with test year 2020.

For each test year:

1. fit both models on BTC observations strictly before that year;
2. evaluate on BTC observations in that year;
3. apply the exact fitted BTC models, unchanged, to ETH observations in the same year.

ETH is therefore a locked BTC→ETH transfer check.

Minimum BTC training support:

- 5,000 rows;
- at least 100 expansion events;
- at least 100 non-events.

## Metrics

For each model, role, and year:

- ROC AUC
- average precision
- Brier score
- top-5% expansion-event lift
- event count/rate

Also report pooled OOS metrics and GBM-minus-logistic AUC deltas by year.

Unlike Experiment 001, logistic is unweighted, so Brier score is an apples-to-apples calibration diagnostic.

## Interpretability

Aggregate absolute standardized logistic coefficients and GBM feature importances across folds.

If GBM shows a meaningful and reasonably persistent ranking/calibration advantage on BTC and locked ETH transfer, the next lab step is to interrogate the dominant nonlinear interaction with simple conditional tables or partial-dependence-style diagnostics. It is not strategy construction.

If logistic matches or beats GBM, treat the volatility-expansion structure as adequately low-dimensional for this feature set and pivot to a different ML use case rather than tuning the model.

## Boundary

Everything here is exploratory and non-confirmatory. No result authorizes Core v1/Core v2/runtime/threshold/order/NAV/exposure/paper/live/capital action.