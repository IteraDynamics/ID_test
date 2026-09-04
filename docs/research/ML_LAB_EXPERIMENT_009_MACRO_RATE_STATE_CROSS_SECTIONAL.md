# ML Lab Experiment 009 — Macro/Rate State + Cross-Sectional Ranking

## Status

**EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY**

No Core/runtime/threshold/order/NAV/exposure/strategy/portfolio/paper/live/capital implication is authorized.

## Motivation

Experiments 005-008 found that price/volume-only nonlinear cross-sectional structure existed historically but was regime-sensitive. Experiment 006 located the major deterioration around the 2022 macro/rates regime shift; Experiments 007-008 showed that shorter training memory repaired much of the deterioration but did not produce a durable GBM-over-Ridge advantage.

Experiment 009 asks whether explicit macro/rate state contains incremental information that the price-only models were otherwise forced to infer indirectly.

## Primary question

> Does adding causal macro/rates state information improve cross-sectional ETF ranking beyond the price/volume-only Ridge and GBM baselines, and does GBM exploit macro × asset-state interactions better than Ridge?

## Frozen ETF universe

Same 14-ETF universe as Experiments 005-008:

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

## Frozen target

Same target as Experiment 005:

- weekly anchors on the common ETF trading calendar;
- 20-session forward return divided by trailing 60-session volatility times sqrt(20);
- within-anchor percentile rank across the 14 ETFs.

No target change is allowed in this experiment.

## Price-state feature block

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

## Frozen macro/rates feature block

Use only four externally observed state variables, deliberately small to avoid a macro kitchen-sink search:

1. **2-year Treasury yield level** — FRED series `DGS2`
2. **10-year Treasury yield level** — FRED series `DGS10`
3. **10y minus 2y yield-curve slope** — derived contemporaneously as `DGS10 - DGS2`
4. **3-month Treasury yield level** — FRED series `DGS3MO`
5. **VIX level** — local `data/VIX_1D.csv` source already present in the repository workflow

Derived transformations are frozen to:

- level percentile over trailing 252 observed trading sessions for each rate/VIX series;
- 20-session change for DGS2, DGS10, DGS3MO, and VIX;
- 10y-2y curve slope level and its 20-session change.

No CPI, unemployment, PMI, Fed-event labels, or other macro series are included in Experiment 009.

## Causal alignment

For each ETF anchor date, each macro/rates value must be the latest observation with timestamp **less than or equal to** the anchor timestamp.

No backward fill from future observations is allowed.

Daily Treasury series are forward-filled only across subsequent ETF sessions after an observed value exists. VIX is aligned the same way.

Any anchor without a complete macro block fails closed and is excluded before model fitting.

## Zero-dollar source and replay rule

Treasury series are acquired from the public FRED CSV endpoint at zero monetary cost.

On first successful run, raw source CSVs are cached under:

`artifacts/ml_lab_experiment_009/source_cache/`

The report records SHA-256 hashes of each cached raw source. Subsequent runs reuse the cache unless the user explicitly deletes it. This preserves local replay stability after acquisition.

VIX uses the existing local `data/VIX_1D.csv` file and its SHA-256 is also recorded.

Acquisition or parsing failure is fatal; the runner does not silently substitute another source.

## Model comparison

No hyperparameter tuning.

Four model variants:

1. `price_ridge`
   - StandardScaler + Ridge(alpha=10.0)
   - 12 price-state features only

2. `price_gbm`
   - GradientBoostingRegressor(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42)
   - 12 price-state features only

3. `macro_ridge`
   - same Ridge definition
   - 12 price-state features + frozen macro/rates block

4. `macro_gbm`
   - same GBM definition
   - 12 price-state features + frozen macro/rates block

## Training memory

Primary Experiment 009 model comparison uses the **trailing 3-year memory** discovered in Experiment 007 because it produced the strongest post-2021 repair while remaining a pre-existing, already-observed memory scheme before Experiment 009.

For guardrail context, the runner also emits the same four-model comparison under the expanding window, but Experiment 009 does not search or tune memory length.

No 5-year or additional memory variants are introduced.

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

## Regime diagnostic

Report 2022-2024 separately.

Central questions:

1. Does macro augmentation repair 2022-2024 ranking quality relative to the corresponding price-only model?
2. Is macro incremental value present in both Ridge and GBM?
3. Does macro GBM gain more than macro Ridge, consistent with useful nonlinear macro × asset-state interactions?

## Interpretation discipline

Positive exploratory evidence requires more than one favorable pooled mean.

Evidence is stronger when:

- macro augmentation improves 2022-2024 IC and tail spread;
- the effect is not driven by one year;
- macro GBM improvement over price GBM exceeds the corresponding Ridge improvement;
- macro feature importance is not dominated by one unstable input.

Negative or mixed evidence should close this formulation rather than trigger feature proliferation or hyperparameter tuning.
