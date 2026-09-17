# Multidimensional market-state study

## Scope and frozen question

Does separating direction, volatility, volatility change and path structure
describe materially different subsequent market behavior better than Core's
unchanged classification? This is classification research, not a trading system,
volatility-sizing experiment or authorization to modify Core V1.

This specification precedes the first market-data run of this prototype. Use the
existing hash-locked BTC/ETH hourly files, 1H and 4H feature construction, daily
UTC-midnight snapshots and expanding annual fits for 2020–2025. These dates have
already been used in earlier research: walk-forward results are development
evidence, not a fresh untouched holdout. No new downloads are necessary.

## Representations

- Existing Core labels, imported through the source-locked research adapter.
- Rule axes: UP/DOWN when EMA spread exceeds +/-0.25 ATR and EMA momentum agrees;
  otherwise NEUTRAL. Volatility LOW/NORMAL/HIGH uses training-only ATR thirds.
  ATR acceleration above +0.10 or below -0.10 defines RISING/FALLING, otherwise
  STABLE. Past-24H absolute net log return divided by total absolute log returns
  defines path efficiency: below 0.30 CHOPPY, at least 0.60 PERSISTENT, else MIXED.
- Joint rule labels have at most 81 combinations. They are candidate descriptions,
  not 81 discovered regimes. No search over thresholds or number of combinations.
- One KMeans model with six clusters, seed 1729, ten initializations. Inputs:
  ATR-normalized EMA spread and momentum, log ATR fraction, ATR acceleration,
  path efficiency. Training-only 1st/99th percentile clipping and standardization.
  Six is a fixed complexity comparator, not an estimate of the true state count.
- Volatility-only partition and continuous-feature controls for incremental value.

Cluster identifiers are local to each asset/timeframe/year. K0 in one fit is not
necessarily K0 in another. Do not pool these labels across folds. Annual refits
also change relative-volatility thresholds; axes describe relative conditions.

## Timing and leakage controls

Inputs reflect completed bars at the snapshot timestamp. Annual fitting uses
only rows whose next-24H label end is strictly before January 1. Outcomes never
enter clustering or representative-snapshot selection. Future data gaps remove
outcome scoring, not otherwise valid historical state assignments. Transitions
require exactly adjacent daily snapshots, and never cross annual refits.

## Outputs and interpretation

States, training/evaluation occupancy, within-year transition probabilities and
representative snapshots are the primary outputs. Representative snapshots are
closest to a training state's feature median, not selected for attractive future
returns. They are examples, not evidence of predictive power. Daily transitions
cannot establish intraday dwell times or transition behavior.

Conditional next-24H return, log realized variance, downside event (any sampled
hourly close at least 3% below entry close), and path efficiency distributions
describe subsequent behavior. There is no assumed ground-truth regime label.
Classification accuracy against invented labels would not establish usefulness.

An identical conditional-mean decoder tests each partition. State estimates
shrink toward the training mean with 20 pseudo-observations. Fewer than 20 training
observations or an unseen state falls back to that mean. Twenty is a diagnostic
support rule, not a statistical sufficiency guarantee. Compare against the global
mean and fixed-alpha standardized Ridge controls using simple and full continuous
features. Use matching valid evaluation rows; no hyperparameter search.

Judge population support, transition stability and conditional behavior across
years/assets, not the prettiest partition or best single score. Multiple related
comparisons are exploratory, with no formal significance claims. If distinctions
are sparse, unstable or add no value beyond continuous inputs, do not promote
them. If supported, freeze a small useful representation before a separate
strategy experiment and reserve genuinely unseen data for later confirmation.

No strategy CAGR/Sharpe claims, execution assumptions, leverage, orders, Core
modifications or promotion decisions are produced by this study. Synthetic tests
establish software behavior only, not market efficacy.
