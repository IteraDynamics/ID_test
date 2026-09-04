# ML Lab Experiment 002 — Volatility Expansion Results

**Branch:** `agent/ml-lab-exploration-20260903`

**Status:** COMPLETE — EXPLORATORY / NON-CONFIRMATORY

**Experiment spec:** `docs/research/ML_LAB_EXPERIMENT_002_VOLATILITY_EXPANSION.md`

## Question

Can a shallow nonlinear GBM predict a 24-hour volatility-expansion state materially better than a competent simple logistic model, and does any lift transfer from BTC to ETH without retuning?

Target: future 24h realized volatility divided by trailing 24h realized volatility >= 1.25.

## Data and evaluation

- BTC hourly primary data, 2018-2025.
- ETH hourly locked transfer data, 2018-2025.
- Expanding annual BTC training.
- OOS test years 2020-2025.
- Each yearly BTC model applied unchanged to ETH in the same test year.
- 52,550 pooled OOS rows per asset-role.

## Pooled result

### BTC OOS

| Model | ROC AUC | Average precision | Brier | Top-5% lift |
|---|---:|---:|---:|---:|
| Naive | 0.4901 | 0.3161 | 0.2177 | 0.984x |
| Logistic | **0.7843** | **0.6464** | **0.1688** | **2.672x** |
| GBM | 0.7814 | 0.6414 | 0.1689 | 2.604x |

BTC event rate: 31.95%.

### Locked BTC→ETH transfer

| Model | ROC AUC | Average precision | Brier | Top-5% lift |
|---|---:|---:|---:|---:|
| Naive | 0.4970 | 0.3046 | 0.2115 | 1.050x |
| Logistic | **0.7757** | 0.5992 | **0.1695** | 2.615x |
| GBM | 0.7725 | **0.6065** | 0.1710 | **2.709x** |

ETH event rate: 30.37%.

## Fold behavior

### BTC OOS — GBM AUC minus Logistic

- 2020: -0.0164
- 2021: -0.0055
- 2022: +0.0124
- 2023: +0.0055
- 2024: -0.0094
- 2025: -0.0032
- GBM wins: 2/6
- Logistic wins: 4/6
- Mean delta: **-0.00277**
- Median delta: **-0.00436**

### ETH transfer — GBM AUC minus Logistic

- 2020: -0.0118
- 2021: +0.0002
- 2022: +0.0001
- 2023: -0.0011
- 2024: -0.0042
- 2025: -0.0041
- GBM wins: 2/6
- Logistic wins: 4/6
- Mean delta: **-0.00348**
- Median delta: **-0.00257**

## Interpretation

### 1. The market-state target is strongly learnable

This is the major finding. A simple BTC-trained logistic model reaches ROC AUC ~0.78 on BTC and ~0.78 on locked ETH transfer. Top-5% observations contain roughly 2.6-2.7x the unconditional expansion-event rate.

The predictive structure therefore appears broad and cross-asset rather than a BTC-only artifact.

### 2. Shallow nonlinear complexity did not earn itself globally

GBM does not improve pooled ROC AUC, average precision, or Brier on BTC, and loses the AUC comparison in four of six BTC years. The same AUC pattern transfers to ETH.

Together with Experiment 001, this is a second distinct target on which a competent logistic model captures essentially all global ranking information available to the shallow GBM from the chosen compact price-state feature vector.

This is evidence against adding nonlinear complexity **for this representation and target**, not evidence against machine learning generally.

### 3. The extreme tail contains a small nonlinear hint

On locked ETH transfer, GBM slightly improves average precision and top-5% event lift despite a slightly worse global AUC:

- AP: 0.6065 vs 0.5992;
- top-5 lift: 2.709x vs 2.615x.

This suggests that any useful nonlinear advantage may live in the highest-risk tail rather than in broad ranking.

This is exploratory and does not establish a real nonlinear edge.

### 4. GBM concentrated on a compact volatility-state geometry

GBM mean importance:

1. `vol_ratio_24_168`: 50.17%
2. `realized_vol_24h`: 23.45%
3. `range_position_168h`: 10.12%
4. `vol_ratio_72_168`: 5.72%
5. `drawdown_from_high_168h`: 2.99%

The model is not behaving like a diffuse 12-feature black box. Roughly three quarters of its importance sits in short-vs-long volatility structure and current short volatility.

This motivates a direct interrogation of the volatility-state relationship rather than a more complex model.

## Decision

Experiment 002 does **not** justify tuning or enlarging the GBM.

It does justify Experiment 003 with two exploratory objectives:

1. expose the empirical relationship between short/long volatility ratio, current volatility state, range position, and future volatility expansion;
2. map simple-vs-GBM performance across a fixed severity surface (future/trailing 24h volatility ratio thresholds 1.25, 1.50, 1.75, 2.00) to test whether nonlinear usefulness increases specifically in rarer tail events.

No threshold from that surface will be selected as a trading rule. The entire surface is exploratory and contaminated.

## Hard boundary

No Experiment 002 result authorizes any Core v1/Core v2 composition, runtime, threshold, order, NAV, exposure, paper/live, execution, or capital change.