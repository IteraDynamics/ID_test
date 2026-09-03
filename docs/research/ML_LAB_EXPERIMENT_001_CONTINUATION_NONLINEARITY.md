# ML Lab Experiment 001 — Continuation Nonlinearity Probe

**Branch:** `agent/ml-lab-exploration-20260903`

**Status:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

**Parent boundary:** `docs/research/ML_LAB_EXPLORATION_CHARTER.md`

## Question

Can a deliberately shallow nonlinear model extract stable chronological predictive structure about short-horizon trend continuation that a competent logistic baseline misses, and does any lift transfer from BTC to ETH without retuning?

This is not a trading-strategy test. It does not evaluate portfolio mapping, Sharpe, sizing, Core v1 changes, or production readiness.

## Why this experiment

Trend Persistence Engine v0 already established that continuation ranking can be predictively learnable. Its strongest validated candidates were logistic models, including BTC immediate ROC AUC ~0.74 and BTC medium ROC AUC ~0.68. That makes logistic regression a real benchmark rather than a straw man.

Experiment 001 deliberately does not rerun the full Trend Persistence program. It narrows the problem to two horizons and a compact state vector so that any GBM lift can be interrogated rather than merely celebrated.

## Data

Primary asset: BTC hourly OHLCV.

Transfer asset: ETH hourly OHLCV.

Expected local research files:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`

No governed campaign holdout is consumed by this exploratory lab.

## Horizons

Exactly two exploratory horizons:

- 24 hours
- 72 hours

## Target

Reuse the causal Trend Persistence target concept.

At time `t`:

1. trend direction = sign of trailing 24-hour return;
2. future return = close at `t+h` divided by close at `t`, minus one;
3. volatility-aware magnitude floor = `max(absolute_floor, realized_vol_24h * sqrt(h))`;
4. continuation = 1 when future return has the same sign as the trailing trend direction and exceeds the magnitude floor;
5. everything else = 0.

Fixed exploratory absolute floors:

- 24h horizon: 1.0%
- 72h horizon: 2.0%

These are inherited in spirit from Trend Persistence v0 and are not optimized in this experiment.

## Feature vector

Twelve causal features, all computed using information available at or before `t`:

1. 1h return
2. 24h return
3. 72h return
4. 168h return
5. 24h-vs-168h SMA trend strength
6. 24h minus 168h return acceleration
7. 24h realized volatility
8. 168h realized volatility
9. 24h / 168h volatility ratio
10. distance from 24h SMA
11. drawdown from 168h rolling high
12. position inside the 168h high-low range

No volume, calendar, regime, funding, or external features are included in Experiment 001. The point is to test nonlinear structure in a compact price-state representation first.

## Models

### Naive

Constant continuation probability equal to the BTC training sample event rate.

### Logistic baseline

- standard scaling fit on BTC training data only;
- `LogisticRegression(C=0.25, class_weight="balanced", max_iter=2000, random_state=42)`.

This matches the historically competent Trend Persistence logistic baseline.

### Shallow GBM

- `GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.04, random_state=42)`.

No hyperparameter search.

## Chronological evaluation

Expanding annual walk-forward beginning with test year 2020.

For each test year:

1. train both models on BTC observations strictly before that calendar year;
2. evaluate on BTC observations in the test year;
3. without refitting or rescaling on ETH, apply the exact BTC-trained estimators to ETH observations in the same test year.

Thus the ETH result is a locked BTC→ETH transfer check, not an independently optimized ETH model.

Minimum BTC training support:

- 5,000 rows;
- at least 40 continuation events;
- at least 40 non-events.

## Metrics

For each model, horizon, asset-role, and year:

- ROC AUC
- average precision
- Brier score
- top-5% continuation lift
- event count

Also report pooled OOS metrics across all eligible years.

The primary exploratory comparison is GBM minus Logistic in pooled ROC AUC, supported by fold-by-fold deltas rather than a single aggregate alone.

## Interpretability output

For each horizon:

- aggregate absolute standardized logistic coefficients across folds;
- aggregate GBM feature importance across folds;
- identify features whose importance ranking differs materially between linear and nonlinear models.

If GBM does not meaningfully improve chronological BTC performance, stop: Experiment 001 has not justified nonlinear follow-up.

If GBM does improve BTC but fails BTC→ETH transfer, treat the lift as likely asset-specific until understood.

If GBM improves both BTC and locked ETH transfer, the next lab step is **not** strategy construction. The next step is to interrogate the top nonlinear interaction with simple conditional tables / partial dependence and ask whether it can be expressed as a simpler hypothesis.

## Interpretation discipline

This is exploratory. There is no institutional pass/fail threshold and no untouched confirmation claim.

Interesting means, qualitatively:

- GBM lift is not confined to one calendar year;
- the pooled lift is large enough to matter relative to ordinary fold noise;
- transfer does not collapse completely;
- feature importance suggests a coherent interaction worth investigating.

Uninteresting means logistic performs as well as or better than GBM, or apparent GBM lift is concentrated in one fold.

## Hard boundary

No result from this experiment authorizes changes to Core v1, Core v2 composition, runtime, thresholds, orders, NAV, exposure, paper/live trading, execution, or capital.