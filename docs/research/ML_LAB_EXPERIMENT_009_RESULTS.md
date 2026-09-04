# ML Lab Experiment 009 — Results

## Status

**EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY**

No Core/runtime/threshold/order/NAV/exposure/strategy/portfolio/paper/live/capital implication is authorized.

## Question

Experiment 009 asked whether explicit macro/rates state improves the 14-ETF cross-sectional ranking problem from Experiments 005-008, and whether nonlinear GBM can exploit macro × asset-state interactions better than Ridge.

The experiment preserved the same 14-ETF universe, 20-session forward risk-adjusted cross-sectional rank target, annual chronological folds, strict target-end embargo, and untouched 2025 Campaign #50 holdout.

The macro-augmented matrix contained the original 12 price-state features, four macro-state variables, and 16 pre-specified macro × asset-state interaction terms. Primary memory was trailing 3 years; expanding memory was emitted as context.

## Data coverage

- common ETF sessions: 5,033
- eligible panel anchors: 978
- eligible panel rows: 13,692
- first eligible anchor: 2005-07-01
- last eligible anchor: 2024-11-27
- 2025 Campaign #50 holdout used: **false**

Zero-dollar external sources were cached and hashed:

- DGS2
- DGS10
- DGS3MO
- VIX

## Full-sample model results

### Expanding memory

| Model | Mean rank IC | Median rank IC | Positive IC fraction | Mean top-bottom raw spread |
|---|---:|---:|---:|---:|
| price_ridge | 0.05600 | 0.05934 | 0.5588 | 0.05763 |
| price_gbm | 0.05454 | 0.04615 | 0.5599 | 0.05928 |
| macro_ridge | 0.03327 | 0.04615 | 0.5410 | 0.02995 |
| macro_gbm | **0.06715** | **0.08571** | **0.6131** | **0.07674** |

Macro augmentation under expanding memory:

- macro Ridge minus price Ridge: **-0.02273 IC**, **-0.02768 spread**
- macro GBM minus price GBM: **+0.01261 IC**, **+0.01746 spread**
- macro GBM minus macro Ridge: **+0.03387 IC**, **+0.04680 spread**

This is the strongest full-sample evidence in the ML Lab that nonlinear interaction structure can add information beyond a linear cross-sectional model when genuinely different information is supplied.

### Trailing 3-year memory

| Model | Mean rank IC | Median rank IC | Positive IC fraction | Mean top-bottom raw spread |
|---|---:|---:|---:|---:|
| price_ridge | 0.05767 | 0.06374 | 0.5665 | 0.06535 |
| price_gbm | 0.04223 | 0.04615 | 0.5576 | 0.04311 |
| macro_ridge | 0.04072 | 0.04176 | 0.5443 | 0.04876 |
| macro_gbm | 0.05818 | 0.05934 | 0.5532 | 0.06579 |

Macro augmentation under trailing-3y memory:

- macro Ridge minus price Ridge: **-0.01695 IC**, **-0.01659 spread**
- macro GBM minus price GBM: **+0.01595 IC**, **+0.02268 spread**
- macro GBM minus macro Ridge: **+0.01746 IC**, **+0.01703 spread**

Macro GBM again benefits relative to price GBM, while macro Ridge deteriorates relative to price Ridge.

## 2022-2024 regime results

### Expanding memory

| Model | Mean rank IC | Mean top-bottom raw spread |
|---|---:|---:|
| price_ridge | 0.02935 | -0.01825 |
| price_gbm | -0.00327 | -0.05044 |
| macro_ridge | **0.04989** | **0.02956** |
| macro_gbm | 0.01737 | -0.01299 |

Macro augmentation improved both expanding models in 2022-2024:

- Ridge: **+0.02054 IC**, **+0.04781 spread**
- GBM: **+0.02065 IC**, **+0.03744 spread**

However, macro Ridge beat macro GBM in this period by **0.03252 IC** and **0.04256 spread**.

### Trailing 3-year memory

| Model | Mean rank IC | Mean top-bottom raw spread |
|---|---:|---:|
| price_ridge | **0.05309** | 0.05649 |
| price_gbm | 0.04789 | **0.07994** |
| macro_ridge | 0.02609 | 0.04014 |
| macro_gbm | 0.03943 | 0.00924 |

Under adaptive 3-year memory, macro augmentation hurt both models in 2022-2024:

- Ridge: **-0.02700 IC**, **-0.01635 spread**
- GBM: **-0.00846 IC**, **-0.07070 spread**

Macro GBM still beat macro Ridge by **+0.01334 IC**, but remained worse than price GBM.

## Feature-importance structure

The macro-augmented GBM placed substantial weight on the pre-specified macro interaction block:

- expanding macro GBM macro-or-interaction importance share: **68.6%**
- trailing-3y macro GBM macro-or-interaction importance share: **73.3%**

Prominent recurring interactions included:

- curve_10y2y_pct252 × vol_60d_xrank
- vix_pct252 × vol_60d_xrank
- curve_10y2y_pct252 × ret_120d_xrank
- rate2_pct252 × vol_60d_xrank
- rate2_pct252 × ret_120d_xrank
- rate2_chg20 × ret_120d_xrank

The macro Ridge also placed material coefficient weight on macro/interactions, especially under trailing-3y memory, but the resulting ranking performance was weaker than its price-only counterpart.

## Interpretation

Experiment 009 supports three exploratory conclusions.

1. **Macro/rates state contains incremental cross-sectional information.** The 2022-2024 expanding comparison shows that explicit macro state repaired both price-only models relative to their expanding baselines.

2. **The information is not well described as a universal additive macro factor.** Macro augmentation hurts Ridge over the full sample and under trailing-3y memory, while it improves GBM over the full sample under both memory schemes.

3. **Nonlinear macro × asset-state interactions are plausible.** Macro GBM consistently improves on price GBM over the full sample, with most model importance concentrated in the frozen macro/interactions block. However, this advantage is memory/regime dependent and does not survive as a simple 2022-2024 superiority claim.

A useful structural hypothesis is that explicit macro state and short training memory are partially substitutable adaptation mechanisms: expanding models benefit from explicit regime context, whereas trailing-3y models already condition heavily on the current regime through recency.

## Classification

**EXPLORATORY_MACRO_INTERACTION_SIGNAL_PRESENT_BUT_REGIME_DEPENDENT**

This is not validation and does not authorize any trading or portfolio implication.

## Next diagnostic

Proceed to Experiment 010 as a no-refit macro-interaction stability/mechanism audit.

The audit should test whether the Experiment 009 macro GBM increment recurs across economically defined rate, curve, and volatility regimes; whether it is concentrated in a small number of ETFs; whether interaction directions are stable; and whether the expanding advantage is disproportionately driven by the historical zero-rate regime.
