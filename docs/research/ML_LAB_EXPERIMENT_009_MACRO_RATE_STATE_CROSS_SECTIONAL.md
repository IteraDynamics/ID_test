# ML Lab Experiment 009 — Macro/Rate State + Cross-Sectional Ranking

## Status

**EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY**

No Core/runtime/threshold/order/NAV/exposure/strategy/portfolio/paper/live/capital implication is authorized.

## Motivation

Experiments 005-008 found that price/volume-only nonlinear cross-sectional structure existed historically but was regime-sensitive. Experiment 006 located the major deterioration around the 2022 macro/rates regime shift; Experiments 007-008 showed that shorter training memory repaired much of the deterioration but did not produce a durable GBM-over-Ridge advantage.

Experiment 009 asks whether explicit macro/rate state contains incremental information that the price-only models were otherwise forced to infer indirectly.

## Primary question

> Does adding causal macro/rates state information improve cross-sectional ETF ranking beyond the price/volume-only Ridge and GBM baselines, and does GBM exploit macro × asset-state interactions better than Ridge?

## Frozen ETF universe and target

Same 14-ETF universe and same target as Experiments 005-008:

RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY.

Target:

- weekly anchors on the common ETF trading calendar;
- 20-session forward return divided by trailing 60-session volatility times sqrt(20);
- within-anchor percentile rank across the 14 ETFs.

No target change is allowed.

## Frozen price-state block

Exactly the same 12 cross-sectional rank features used in Experiments 005-008:

- ret_5d_xrank
- ret_20d_xrank
- ret_60d_xrank
- ret_120d_xrank
- vol_20d_xrank
- vol_60d_xrank
- vol_ratio_20_60_xrank
- distance_sma_20_xrank
- distance_sma_120_xrank
- drawdown_120_xrank
- range_position_120_xrank
- volume_z_60_xrank

## Frozen external state sources

Use only these zero-dollar external state sources:

1. 2-year Treasury yield — FRED `DGS2`
2. 10-year Treasury yield — FRED `DGS10`
3. 3-month Treasury yield — FRED `DGS3MO`
4. VIX — existing local `data/VIX_1D.csv`

The 10y-minus-2y curve slope is derived contemporaneously from DGS10-DGS2.

No CPI, unemployment, PMI, Fed-event labels, or additional macro series are included.

## Frozen macro-state representation

A raw macro value is identical for every ETF at a given anchor and therefore cannot by itself alter a within-anchor ranking in an additive linear model. To avoid structurally handicapping Ridge, Experiment 009 freezes a small interaction representation **before any outcomes are inspected**.

Four macro state variables:

1. `rate2_pct252` — trailing-252-observation percentile of DGS2
2. `curve_10y2y_pct252` — trailing-252-observation percentile of DGS10-DGS2
3. `rate2_chg20` — 20-session change in DGS2
4. `vix_pct252` — trailing-252-observation percentile of VIX

Four asset-state interaction bases, selected from the already-observed dominant Experiment 005-007 price-state family rather than from Experiment 009 outcomes:

- ret_120d_xrank
- vol_60d_xrank
- vol_ratio_20_60_xrank
- drawdown_120_xrank

The macro-augmented feature matrix contains:

- the original 12 price-state features;
- the four raw macro state variables;
- all 4×4 = 16 products between the frozen macro states and frozen asset-state bases.

Total macro-augmented feature count: 32.

Both Ridge and GBM receive the **same 32-feature augmented matrix**. This allows Ridge to use explicit regime interactions while still allowing GBM to model further nonlinear structure.

No other macro transformations or interaction terms are allowed in Experiment 009.

## Causal alignment

For each ETF anchor date, every macro/rate value must be the latest observation with timestamp less than or equal to the anchor timestamp.

No backward fill from future observations is allowed.

Treasury series may be forward-filled only across subsequent ETF sessions after an observed value exists. VIX is aligned the same way.

Any anchor without a complete macro block fails closed and is excluded before model fitting.

## Zero-dollar source and replay rule

Treasury series are acquired from the public FRED CSV endpoint at zero monetary cost.

On first successful run, raw source CSVs are cached under:

`artifacts/ml_lab_experiment_009/source_cache/`

The report records SHA-256 hashes of each cached raw source. Subsequent runs reuse the cache unless explicitly deleted, preserving local replay stability after acquisition.

VIX uses `data/VIX_1D.csv`; its SHA-256 is recorded.

Acquisition or parsing failure is fatal. No substitute source is permitted.

## Model comparison

No hyperparameter tuning.

Four variants:

1. `price_ridge`: StandardScaler + Ridge(alpha=10.0), original 12 price features
2. `price_gbm`: GradientBoostingRegressor(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42), original 12 price features
3. `macro_ridge`: same Ridge definition, frozen 32-feature augmented matrix
4. `macro_gbm`: same GBM definition, frozen 32-feature augmented matrix

## Training memory

Primary comparison uses the **trailing 3-year memory** already studied in Experiment 007 because it produced the strongest post-2021 repair.

For guardrail context, the runner also emits the same four-model comparison under the expanding window. No 5-year or new memory variants are introduced.

## Chronological evaluation

- annual test folds;
- strict target-end embargo exactly as in Experiments 005 and 007;
- no 2025 Campaign #50 holdout use;
- last allowed outcome date: 2024-12-31;
- test years begin only when macro/rates coverage and minimum training support are sufficient.

## Primary diagnostics

For each memory scheme and model:

- pooled mean/median rank IC;
- positive-IC fraction;
- mean/median top-minus-bottom raw target spread;
- annual metrics.

Incremental comparisons:

- macro_ridge minus price_ridge;
- macro_gbm minus price_gbm;
- macro_gbm minus macro_ridge;
- price_gbm minus price_ridge.

Report 2022-2024 separately.

Central questions:

1. Does macro augmentation repair 2022-2024 ranking quality relative to the corresponding price-only model?
2. Is macro incremental value present in both Ridge and GBM?
3. Does macro GBM gain more than macro Ridge, consistent with useful nonlinear macro × asset-state interactions?

## Interpretation discipline

Positive exploratory evidence requires more than one favorable pooled mean. Stronger evidence requires improvement in 2022-2024, more than one favorable year, and no domination by one unstable macro input.

Negative or mixed evidence closes this formulation rather than triggering feature proliferation or hyperparameter tuning.
