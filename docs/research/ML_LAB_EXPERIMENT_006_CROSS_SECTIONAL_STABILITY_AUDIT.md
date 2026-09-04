# ML Lab Experiment 006 — Cross-Sectional Nonlinear Stability Audit

**Status:** EXPLORATORY / DIAGNOSTIC / NON-CONFIRMATORY  
**Parent:** Experiment 005  
**Branch:** `agent/ml-lab-exploration-20260903`

## Question

Why did GBM's cross-sectional advantage over Ridge reverse after 2021?

Experiment 006 is a diagnostic audit only. It does not retrain with new settings, optimize hyperparameters, shorten the training window, alter features, or search for a replacement model.

## Inputs

Required Experiment 005 artifacts:

- `artifacts/ml_lab_experiment_005/experiment_005_oos_predictions.csv`
- `artifacts/ml_lab_experiment_005/experiment_005_feature_importance_by_fold.csv`
- `artifacts/ml_lab_experiment_005/experiment_005_yearly_metrics.csv`
- `artifacts/ml_lab_experiment_005/experiment_005_asset_diagnostics.csv`

The runner may deterministically rebuild the same causal feature/target panel from the same 14 Campaign #50 ETF files solely to compute descriptive feature/target diagnostics. It must not consume 2025 data and must not fit any predictive model.

## Frozen inherited design

Universe:

`RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY`

Cutoff: `2024-12-31`.

Target: within-anchor percentile rank of forward 20-session return divided by trailing 60-session volatility times `sqrt(20)`.

Feature set: identical to Experiment 005.

## Diagnostics

### 1. Simple feature IC by year

For every feature and test year 2012-2024, calculate the mean cross-sectional Spearman IC between the feature rank and target rank across anchors.

This asks whether the raw relationship itself changed before versus after 2021.

### 2. Feature importance / coefficient evolution

Use Experiment 005's saved annual Ridge coefficient magnitudes and GBM feature importances.

Report:

- annual top features;
- pre-2022 mean importance;
- 2022-2024 mean importance;
- absolute change in importance share.

No refitting.

### 3. Conditional feature geometry

For the top Experiment 005 feature families (`vol_60d_xrank`, `ret_120d_xrank`, `vol_ratio_20_60_xrank`, `drawdown_120_xrank`, `vol_20d_xrank`), compare target rank by feature quintile in:

- pre-2022 test anchors: 2012-2021;
- post-2021 test anchors: 2022-2024.

This diagnoses monotonicity, curvature, sign changes, and flattening.

### 4. Asset concentration

From saved OOS predictions, calculate per model/ticker:

- mean absolute rank error;
- mean signed centered-rank contribution;
- pre/post difference;
- share of aggregate GBM-minus-Ridge rank-error deterioration attributable to each ticker.

The goal is to distinguish broad deterioration from one-sector or one-ETF domination.

### 5. Prediction-dispersion stability

For each year/model, calculate cross-sectional score dispersion at each anchor and summarize:

- mean score standard deviation;
- median score standard deviation;
- target-rank dispersion (control);
- GBM versus Ridge score-dispersion ratio.

This can reveal whether GBM became overconfident/under-dispersed after 2021.

### 6. Tail error

At each anchor/model, identify predicted top and bottom quartiles and measure:

- mean actual target rank of predicted top quartile;
- mean actual target rank of predicted bottom quartile;
- top-minus-bottom target-rank spread;
- extreme rank-error rate for the top/bottom quartiles.

Summarize by year and pre/post period.

## Interpretation categories

The runner should not force a causal conclusion. It should produce evidence for one or more of these descriptive categories:

- `RELATIONSHIP_SHIFT`: simple feature/target relationships materially changed after 2021;
- `MODEL_BRITTLENESS`: raw feature relationships persisted but GBM ranking quality deteriorated more than Ridge;
- `ASSET_CONCENTRATION`: deterioration is dominated by a narrow subset of ETFs;
- `TAIL_FAILURE`: broad IC is less affected than extreme ranking behavior;
- `MIXED_OR_UNRESOLVED`: no single explanation dominates.

These are descriptive labels, not validation decisions.

## Hard boundary

No 2025 holdout use. No model tuning. No alternative training window. No new predictor family. No strategy, portfolio, runtime, execution, NAV, exposure, paper/live, or capital action.