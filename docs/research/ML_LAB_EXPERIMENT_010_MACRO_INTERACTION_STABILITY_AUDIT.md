# ML Lab Experiment 010 — Macro Interaction Stability Audit

## Status

**EXPLORATORY / DIAGNOSTIC / NON-CONFIRMATORY**

No Core/runtime/threshold/order/NAV/exposure/strategy/portfolio/paper/live/capital implication is authorized.

## Motivation

Experiment 009 found that explicit macro/rates state can improve cross-sectional ETF ranking, especially for GBM over the full sample, but the benefit was strongly dependent on training memory and regime.

Experiment 010 does **not** search for a better model. It audits the existing Experiment 009 outputs to determine whether the apparent macro interaction value is structurally recurring or mainly a calendar/regime artifact.

## Primary question

> Does the macro-augmented GBM's incremental value recur across economically distinct rate, curve, and volatility states, or is the result concentrated in old zero-rate history, a few ETFs, or isolated regimes?

## Source artifacts

Primary inputs are existing Experiment 009 artifacts:

- `artifacts/ml_lab_experiment_009/experiment_009_oos_predictions.csv`
- `artifacts/ml_lab_experiment_009/experiment_009_macro_state.csv`
- `artifacts/ml_lab_experiment_009/experiment_009_feature_importance_by_fold.csv`
- `artifacts/ml_lab_experiment_009/experiment_009_yearly_metrics.csv`

The runner may deterministically rebuild the Experiment 005 price-state panel solely to recover the four pre-specified asset-state bases used by Experiment 009:

- `ret_120d_xrank`
- `vol_60d_xrank`
- `vol_ratio_20_60_xrank`
- `drawdown_120_xrank`

No model refit is permitted.

## Frozen models and memories audited

Models:

- price_ridge
- price_gbm
- macro_ridge
- macro_gbm

Memory schemes:

- expanding
- trailing_3y

No new memory length, feature, target, hyperparameter, or model family may be introduced.

## Frozen regime definitions

### 1. Relative 2-year rate state

Using Experiment 009's `rate2_pct252`:

- `rate2_low`: < 1/3
- `rate2_mid`: >= 1/3 and < 2/3
- `rate2_high`: >= 2/3

These are trailing-state percentiles already frozen before Experiment 010.

### 2. Yield-curve state

Using raw contemporaneous `curve_10y2y` in percentage points:

- `curve_inverted`: < 0.0
- `curve_flat`: >= 0.0 and < 1.0
- `curve_steep`: >= 1.0

This is an economically interpretable absolute-state partition, not a sample-optimized cut.

### 3. VIX state

Using Experiment 009's `vix_pct252`:

- `vix_low`: <= 0.5
- `vix_high`: > 0.5

### 4. Zero-rate-history diagnostic

Using raw DGS2:

- `zirp_like`: DGS2 < 0.5%
- `non_zirp`: DGS2 >= 0.5%

This diagnostic directly tests whether the expanding macro GBM result is disproportionately dependent on the low-rate historical regime.

## Model-performance diagnostics

For every regime state and memory scheme, compute anchor-level summaries for:

- price_gbm
- macro_gbm
- macro_ridge
- price_ridge

Metrics:

- mean rank IC
- median rank IC
- positive-IC fraction
- mean top-minus-bottom raw target spread
- median top-minus-bottom raw target spread
- eligible anchor count

Central increments:

- macro_gbm minus price_gbm
- macro_ridge minus price_ridge
- macro_gbm minus macro_ridge

Each increment is computed within the same regime subset and memory scheme.

## Regime recurrence criteria

These are descriptive, not validation gates.

Macro GBM evidence is stronger when:

- macro_gbm minus price_gbm is positive in more than one rate state;
- it is positive in both low and high VIX states;
- it is not confined to `zirp_like` history;
- macro_gbm minus macro_ridge is not driven solely by one regime;
- the effect appears under both expanding and trailing-3y memory, even if magnitude differs.

Mixed or negative recurrence should be reported directly rather than repaired by redefining regimes.

## Interaction-direction diagnostics

For each anchor, compute the cross-sectional Spearman relationship between each frozen asset-state base and the realized target rank.

Then summarize those anchor-level feature ICs by macro regime.

This asks whether, for example, high relative volatility or strong 120-day trend changes sign or strength depending on rate/curve/VIX state.

No new feature family is created; this is descriptive geometry of already-frozen Experiment 009 interaction bases.

## Feature-importance stability

Using saved Experiment 009 fold importances, report for macro_gbm and macro_ridge:

- mean importance by feature and test year;
- pre-2022 vs 2022-2024 importance shifts;
- concentration share of top 3 macro/interaction features;
- whether the same interaction families recur across folds.

No SHAP refit or alternative explainer is introduced.

## Asset-concentration diagnostic

Using saved OOS predictions, compute per ticker the contribution to macro_gbm minus price_gbm ranking improvement.

At minimum report:

- mean absolute rank-error improvement by ticker;
- mean centered-rank-product improvement by ticker;
- share of positive total improvement attributable to top 3 tickers;
- pre-2022 vs 2022-2024 concentration.

A broad result is more credible than one dominated by a few ETFs.

## Calendar-period context

Report:

- pre-2022
- 2022-2024

These are context summaries only. Experiment 010's primary organization is by macro state, not calendar period.

## Holdout and governance boundary

- no 2025 Campaign #50 holdout use;
- no model refit;
- no tuning;
- no runtime or portfolio implication;
- no promotion claim.

## Output artifacts

The runner should emit:

- `experiment_010_report.json`
- `experiment_010_regime_model_summary.csv`
- `experiment_010_regime_increment_summary.csv`
- `experiment_010_feature_ic_by_regime.csv`
- `experiment_010_importance_stability.csv`
- `experiment_010_asset_attribution.csv`
- `experiment_010_zirp_diagnostic.csv`

## Interpretation discipline

Experiment 010 should answer mechanism and recurrence questions only.

A favorable result does not validate a strategy. An unfavorable result closes this particular macro-interaction formulation rather than triggering additional regime partitions, feature proliferation, memory tuning, or hyperparameter search.
