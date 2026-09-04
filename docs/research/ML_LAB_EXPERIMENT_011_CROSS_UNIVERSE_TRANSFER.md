# ML Lab Experiment 011 — Cross-Universe Macro-Interaction Transfer

## Status

**EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY**

No Core/runtime/threshold/order/NAV/exposure/strategy/portfolio/paper/live/capital implication is authorized.

## Motivation

Experiments 009-010 produced the strongest positive ML finding in the lab so far: explicit macro/rates state improved a shallow GBM's cross-sectional ranking in the original 14-ETF U.S. equity universe across multiple rate, curve, VIX, and non-ZIRP regimes.

The main unresolved weakness is universe concentration. All fitted evidence still comes from one domestic-equity cross-section, and post-2022 improvements can be concentrated in a few ETFs.

Experiment 011 therefore tests **transfer**, not a fresh local fit.

## Primary question

> If annual Ridge/GBM models are trained only on the original U.S. 14-ETF universe, does the same frozen feature representation rank a distinct international country-ETF cross-section when applied unchanged?

This is intentionally stronger than retraining the same architecture on a second universe.

## Source training universe

Exactly the original Experiment 005-010 U.S. universe:

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

No source-universe change.

## Frozen destination transfer universe

A separate 14-country ETF cross-section selected before any Experiment 011 outcomes are inspected:

- EWA — Australia
- EWC — Canada
- EWG — Germany
- EWH — Hong Kong
- EWI — Italy
- EWJ — Japan
- EWL — Switzerland
- EWM — Malaysia
- EWW — Mexico
- EWP — Spain
- EWS — Singapore
- EWT — Taiwan
- EWU — United Kingdom
- EWZ — Brazil

Selection rationale:

- U.S.-listed daily ETFs, so observations share the same trading venue/calendar convention as the source universe;
- economically heterogeneous countries/regions rather than U.S. sectors/styles;
- long-history country ETFs preferred to maximize common pre-2022 and post-2022 coverage;
- no destination member appears in the source training universe;
- no destination was selected based on Experiment 011 outcomes.

The acquisition/preflight step must fail closed if the common destination history is too short to support the frozen feature window and chronological folds.

## Source acquisition boundary

Destination OHLCV is zero-dollar research data acquired with Itera's existing canonical `scripts/download_equity_data.py` yfinance workflow.

Destination files are isolated under:

`data/ml_lab_transfer_011/`

The requested source interval is:

- start: `2004-01-01`
- end: `2025-01-01` (exclusive in yfinance; intended last usable date 2024-12-31)
- interval: daily
- `auto_adjust=False`

Experiment 011 never reads destination observations after 2024-12-31.

Each source must match the canonical schema:

`timestamp,open,high,low,close,volume`

The runner records SHA-256, row count, first date, and last date for every destination source.

Missing, malformed, stale, or insufficient sources fail closed.

## Frozen target

The destination target is constructed **within the destination cross-section** using exactly the Experiment 005 definition:

- weekly anchors every five common destination sessions;
- 20-session forward return;
- divide by trailing 60-session realized volatility × sqrt(20);
- percentile-rank the resulting risk-adjusted forward outcome across the 14 destination ETFs at each anchor.

No target change.

## Frozen price-state representation

For each destination anchor, compute the same 12 cross-sectional percentile-rank price/volume features as Experiments 005-010:

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

The feature semantics therefore transfer, while the underlying assets are different.

## Frozen macro representation

Use the exact Experiment 009 macro-state artifact and exact frozen interaction representation:

Macro states:

- `rate2_pct252`
- `curve_10y2y_pct252`
- `rate2_chg20`
- `vix_pct252`

Interaction bases:

- `ret_120d_xrank`
- `vol_60d_xrank`
- `vol_ratio_20_60_xrank`
- `drawdown_120_xrank`

Augmented matrix:

- 12 price features;
- 4 macro states;
- all 16 frozen macro × asset-state products;
- total 32 features.

No new macro series, transformations, or interactions are allowed.

The macro-state values are identical to those used in Experiment 009 and are read from:

`artifacts/ml_lab_experiment_009/experiment_009_macro_state.csv`

## Models

Exactly the same four variants:

1. `price_ridge` — StandardScaler + Ridge(alpha=10.0), 12 price features
2. `price_gbm` — GradientBoostingRegressor(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42), 12 price features
3. `macro_ridge` — same Ridge, frozen 32-feature augmented matrix
4. `macro_gbm` — same GBM, frozen 32-feature augmented matrix

No hyperparameter tuning.

## Memory schemes

Exactly the two Experiment 009 schemes:

- expanding
- trailing 3 years

No new memory length.

## True-transfer fitting rule

For each annual test year and memory scheme:

1. build the source U.S. training panel only;
2. apply the same strict target-end embargo used in Experiments 005/007/009;
3. fit each model on **U.S. source rows only**;
4. reproduce the corresponding U.S. source-year prediction and compare it to saved Experiment 009 OOS predictions as a deterministic parity check;
5. if parity fails beyond numerical tolerance, fail closed;
6. apply the exact fitted source model, scaler, coefficients/trees, and feature ordering unchanged to the destination-country test panel for that same year;
7. never use destination outcomes or rows for fitting, scaling, hyperparameter choice, feature selection, or memory selection.

This is model transfer, not destination retraining.

## Chronological boundary

- destination outcomes stop at 2024-12-31;
- Campaign #50's reserved 2025 U.S. holdout remains untouched;
- destination 2025 data are neither acquired for analysis nor used;
- annual source training uses only labels whose target end date is strictly before the test-year start;
- destination test years are emitted only when all 14 destination assets and complete macro features are available.

## Primary diagnostics

For the destination transfer panel, by memory scheme and model:

- mean/median cross-sectional rank IC;
- positive-IC fraction;
- mean/median top-minus-bottom raw target spread;
- yearly metrics.

Incremental comparisons:

- macro GBM minus price GBM;
- macro Ridge minus price Ridge;
- macro GBM minus macro Ridge;
- price GBM minus price Ridge.

Transfer comparison:

- source U.S. OOS mean IC versus destination mean IC;
- sign preservation of macro-GBM increment;
- transfer-retention ratio = destination macro-GBM increment / source macro-GBM increment, reported descriptively when the source denominator is nonzero;
- pre-2022 versus 2022-2024 transfer;
- destination asset concentration of macro-GBM improvement.

## Interpretation discipline

The strongest exploratory evidence would be:

- macro GBM minus price GBM remains positive in the destination universe;
- positive transfer is not confined to one year;
- the sign survives both pre-2022 and post-2022 periods or has a coherent regime explanation;
- destination macro-GBM improvement is not dominated by a few country ETFs;
- source-model parity checks pass exactly/within floating-point tolerance.

A destination failure must not be rescued by changing the destination universe, fitting on destination data, changing the feature block, or tuning the GBM.

## What Experiment 011 cannot establish

Even a positive result remains exploratory and discovery-contaminated. It does not authorize:

- a trading strategy;
- Core v1 or Core v2 changes;
- asset allocation;
- live or paper deployment;
- capital use;
- calling the mechanism validated.

A positive transfer result would only justify a separate governed confirmation design with untouched data/universe boundaries.
