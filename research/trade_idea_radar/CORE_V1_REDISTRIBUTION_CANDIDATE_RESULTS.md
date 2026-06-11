# Core v1 Redistribution Candidate Results

## Purpose

This memo documents the Core v1 redistribution tests run after sleeve contribution and ablation analysis identified potential capital-efficiency issues in the baseline allocation.

The objective is not maximum robustness at all costs, and not maximum CAGR at any cost. The Core v1 objective is:

> Best attainable portfolio performance while remaining institutionally protective and responsible with capital.

## Baseline

Canonical Core v1 baseline allocation:

| Sleeve / Family | Allocation |
|---|---:|
| Trend | 40% |
| Equity | 35% |
| Gold | 15% |
| Hedge | 10% |
| Mean reversion | 0% |

Canonical baseline, 2020-2025 OOS:

| Metric | Baseline |
|---|---:|
| CAGR | 18.51% |
| Total return | 177.01% |
| Max drawdown | -17.88% |
| Sharpe | 1.223 |
| Calmar | 1.035 |
| Final equity | 277,005.29 |

Annual returns:

| Year | Return |
|---:|---:|
| 2020 | 42.57% |
| 2021 | 25.17% |
| 2022 | -8.65% |
| 2023 | 28.56% |
| 2024 | 24.26% |
| 2025 | 5.02% |

## Execution costs

These tests already include the existing backtest execution model: crypto taker fees, equity ETF fees, dynamic slippage, and spread costs.

Default runner assumptions include:

- Crypto fee: 6 bps.
- Equity ETF fee: 1 bp.
- Base crypto slippage: 3 bps.
- Dynamic crypto slippage component tied to ATR / volatility.
- Spread, fee, and slippage costs are included in sleeve trade accounting.

Therefore, the next validation layer is not "add fees/slippage." It is harsher execution-cost sensitivity: verify that the ranking survives more conservative fee/slippage assumptions.

## Runner parity

The candidate WFO runner reproduced the canonical baseline exactly:

| Metric | Expected | Actual | Diff |
|---|---:|---:|---:|
| CAGR | 18.51% | 18.51% | 0.00 |
| Max drawdown | -17.88% | -17.88% | 0.00 |
| Sharpe | 1.223 | 1.223 | 0.000 |
| Calmar | 1.035 | 1.035 | 0.000 |
| Final equity | 277,005.29 | 277,005.29 | 0.00 |

This confirms the candidate tests are apples-to-apples versus the accepted baseline.

## Candidate summary

| Scenario | CAGR | MaxDD | Sharpe | Calmar | Final equity | 2022 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 18.51% | -17.88% | 1.223 | 1.035 | 277,005.29 | -8.65% | 5.02% |
| candidate_btc1h_hedges_to_btc4h_gld_qqq | 20.19% | -17.50% | 1.341 | 1.154 | 301,430.75 | -9.62% | 9.32% |
| candidate_btc1h_half_btc4h_half_qqq | 19.22% | -16.92% | 1.298 | 1.136 | 287,100.00 | -8.74% | 7.12% |
| candidate_hedges_to_qqq | 19.92% | -18.06% | 1.285 | 1.103 | 297,342.86 | -9.42% | 6.46% |
| candidate_btc1h_to_btc4h | 19.78% | -17.81% | 1.274 | 1.111 | 295,214.01 | -8.86% | 5.31% |
| candidate_eth4h_to_eth1h | 19.04% | -18.27% | 1.249 | 1.042 | 284,543.11 | -7.84% | 4.55% |

## Delta versus baseline

| Scenario | CAGR delta | MaxDD delta | Sharpe delta | Calmar delta | Final equity delta | 2022 delta | 2025 delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| candidate_btc1h_hedges_to_btc4h_gld_qqq | +1.68 | +0.38 | +0.118 | +0.119 | +24,425.46 | -0.97 | +4.30 |
| candidate_btc1h_half_btc4h_half_qqq | +0.71 | +0.96 | +0.075 | +0.101 | +10,094.71 | -0.09 | +2.10 |
| candidate_hedges_to_qqq | +1.41 | -0.18 | +0.062 | +0.068 | +20,337.57 | -0.77 | +1.44 |
| candidate_btc1h_to_btc4h | +1.27 | +0.07 | +0.051 | +0.076 | +18,208.72 | -0.21 | +0.29 |
| candidate_eth4h_to_eth1h | +0.53 | -0.39 | +0.026 | +0.007 | +7,537.82 | +0.81 | -0.47 |

Positive MaxDD delta means less severe drawdown than baseline.

## Stress validation

Rolling stress windows from stitched OOS NAV:

| Scenario | Worst 21d | Worst 63d | Worst 126d |
|---|---:|---:|---:|
| baseline_40_35_15_10 | -11.023% | -11.694% | -14.600% |
| candidate_btc1h_hedges_to_btc4h_gld_qqq | -12.272% | -12.480% | -13.595% |
| candidate_btc1h_half_btc4h_half_qqq | -10.845% | -11.650% | -13.797% |
| candidate_hedges_to_qqq | -12.873% | -13.604% | -14.503% |
| candidate_btc1h_to_btc4h | -10.163% | -10.971% | -14.190% |
| candidate_eth4h_to_eth1h | -10.247% | -13.191% | -16.435% |

The leading aggressive candidate has modestly worse 21d and 63d rolling stress than baseline, but a better 126d rolling stress window and better full-period MaxDD.

Key stress-window interpretation:

- COVID 2020 and 2022 acute stress behavior are modestly worse for the aggressive candidate.
- 2025 chop behavior is materially better.
- Full-period MaxDD is better than baseline.
- Worst major drawdown recovery profile is not worse than baseline.

## Interpretation

The leading candidate is:

`candidate_btc1h_hedges_to_btc4h_gld_qqq`

Plain-English allocation thesis:

> Core v1 performs better when it reduces noisy short-horizon BTC trend and expensive hedge sleeve capital, then reallocates that capital toward cleaner BTC 4H trend, GLD ballast, and QQQ compounding.

This candidate does not eliminate downside risk. It reallocates capital toward a better compensated risk profile.

The key tradeoff is acceptable under the Core v1 objective:

- It materially improves CAGR, Sharpe, Calmar, final equity, 2025 return, and full-period MaxDD.
- It modestly worsens 2022 annual return and acute 21d/63d rolling stress.
- It improves worst 126d rolling stress and full-period MaxDD.

## Decision

Promote `candidate_btc1h_hedges_to_btc4h_gld_qqq` as the leading Core v1 allocation candidate for second-pass validation.

This is a research promotion only. It is not yet a production/default allocation change.

## Current ranking

1. `candidate_btc1h_hedges_to_btc4h_gld_qqq`
   - Leading Core v1 allocation candidate.
2. `candidate_btc1h_half_btc4h_half_qqq`
   - Conservative fallback and clean drawdown-profile candidate.
3. `candidate_btc1h_to_btc4h`
   - Higher crypto-trend variant, but less balanced than the leading candidate.
4. `candidate_hedges_to_qqq`
   - Return improvement, but not as institutionally clean.
5. `candidate_eth4h_to_eth1h`
   - Marginal improvement; not promoted.

## Required next validation layer

Before production promotion, run second-pass validation:

1. Harsher execution-cost sensitivity, using higher-than-default fees/slippage assumptions.
2. Capital scale sensitivity.
3. Longer history if available.
4. Regime-specific attribution.
5. Parameter-freeze / walk-forward integrity check.
6. Forward paper shadow run.

## Artifacts

Generated locally under:

- `artifacts/core_v1_candidate_wfo/*/summary.csv`
- `artifacts/core_v1_candidate_wfo/*/stitched_oos_nav.csv`
- `artifacts/core_v1_candidate_wfo/validation/validation_summary.csv`
- `artifacts/core_v1_candidate_wfo/validation/stress_windows.csv`
- `artifacts/core_v1_candidate_wfo/validation/worst_drawdown_episodes.csv`
