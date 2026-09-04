# ML Lab Experiment 005 — Results

**Experiment:** Cross-Sectional ETF Ranking  
**Status:** EXPLORATORY / NON-CONFIRMATORY  
**Branch:** `agent/ml-lab-exploration-20260903`

## Question

Can shallow nonlinear ML rank a heterogeneous cross-section of liquid ETFs better than a linear model when both receive the same causal cross-sectional state features?

## Design recap

Universe: 14 domestic equity/breadth/style/sector ETFs inherited from Campaign #50:

`RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY`

The experiment intentionally stopped at `2024-12-31`, so Campaign #50's reserved 2025 holdout was not consumed.

Weekly-equivalent anchors were formed every five common sessions. The target was the within-anchor percentile rank of forward 20-session return divided by trailing 60-session volatility times `sqrt(20)`.

Models:

- naive trailing-60-session momentum rank;
- Ridge regression with standard scaling;
- shallow GBM with fixed hyperparameters.

Annual expanding evaluation began in 2012 with a target-horizon embargo so no training target crossed into the test year.

## Sample

- common sessions: 5,033
- first common session: 2005-01-03
- last common session: 2024-12-31
- panel anchors: 979
- panel rows: 13,706
- eligible OOS anchors: 650

## Pooled results

| Model | Mean rank IC | Median rank IC | Positive-IC fraction | Mean top-minus-bottom raw target |
|---|---:|---:|---:|---:|
| GBM | 0.07725 | 0.08132 | 58.15% | 0.08777 |
| Ridge | 0.06382 | 0.07253 | 56.62% | 0.06087 |
| Naive 60d momentum | 0.00241 | 0.02418 | 52.00% | -0.00895 |

GBM therefore improved mean IC over Ridge by about 0.0134 absolute, roughly 21% relative to Ridge's mean IC. Its mean top-minus-bottom separation was about 44% larger than Ridge's.

## Year-by-year GBM minus Ridge mean IC

- 2012: +0.0480
- 2013: +0.0012
- 2014: +0.0014
- 2015: +0.0102
- 2016: +0.0635
- 2017: +0.0158
- 2018: +0.0447
- 2019: +0.0283
- 2020: +0.0139
- 2021: +0.0397
- 2022: -0.0132
- 2023: -0.0424
- 2024: -0.0412

The nonlinear advantage was therefore broadly positive from 2012 through 2021, then reversed for three consecutive years beginning in 2022.

## Feature structure

GBM mean importance was concentrated in:

1. `vol_60d_xrank` — 0.2863
2. `ret_120d_xrank` — 0.2256
3. `vol_ratio_20_60_xrank` — 0.1039
4. `drawdown_120_xrank` — 0.0930
5. `vol_20d_xrank` — 0.0544

Ridge emphasized the same broad state families, especially 60d volatility, 120d trend/distance, and medium-term return state, but could only combine them additively.

## Interpretation

Experiment 005 is the first ML Lab result in which nonlinear ML produced a plausible incremental advantage over a competent linear baseline.

The result is not interpreted as validation or as a trading signal. The important finding is narrower:

> Cross-sectional heterogeneous state appears to be a materially better setting for nonlinear ML than the single-asset price-state classification problems tested in Experiments 001-004.

However, the 2022-2024 reversal is a major stability concern. The next question is not whether a different GBM configuration can repair those years. The next question is whether the underlying feature/target relationships changed, whether the GBM became concentrated in particular assets or tails, or whether an expanding nonlinear model became brittle to a changed cross-sectional regime.

## Required next step

Experiment 006 is a stability audit only. It must not alter:

- the universe;
- target;
- feature set;
- Ridge configuration;
- GBM configuration;
- annual folds;
- training window;
- 2025 holdout boundary.

It should diagnose:

- simple feature rank IC by year;
- feature importance/coefficient evolution by year;
- pre-2022 versus 2022-2024 feature/target conditional structure;
- asset-level error/contribution concentration;
- model score dispersion and tail error by year;
- whether the post-2021 deterioration is broad or attributable to a narrow subset of assets/features.

No result from this exploratory experiment authorizes Core v1/Core v2/runtime/threshold/order/NAV/exposure/paper/live/capital action.