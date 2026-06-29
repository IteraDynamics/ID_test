# Core v1 Cost Sensitivity Validation

## Purpose

This memo documents the Core v1 execution-cost sensitivity validation for the leading redistribution candidates.

The objective is not to find the exact cost level where the strategy eventually breaks. The objective is to verify whether the leading candidate remains superior to the baseline under materially harsher fee and slippage assumptions.

Core v1 objective:

> Best attainable portfolio performance while remaining institutionally protective and responsible with capital.

## Data provenance

The validation uses the canonical 2018-2025 BTC and ETH hourly files:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`

Earlier non-parity reruns using 2019-start crypto files were rejected as data-provenance drift. With the 2018-2025 files, the candidate WFO runner reproduced the accepted baseline exactly at default costs.

## Baseline allocation

Canonical Core v1 baseline:

| Sleeve / Family | Allocation |
|---|---:|
| Trend | 40% |
| Equity | 35% |
| Gold | 15% |
| Hedge | 10% |
| Mean reversion | 0% |

Sleeve-level baseline:

| Sleeve | Allocation |
|---|---:|
| BTC 1H trend | 10.0% |
| BTC 4H trend | 10.0% |
| ETH 1H trend | 10.0% |
| ETH 4H trend | 10.0% |
| BTC hedge | 5.0% |
| ETH hedge | 5.0% |
| SPY | 17.5% |
| QQQ | 17.5% |
| GLD | 15.0% |

## Leading candidate

Leading candidate:

`candidate_btc1h_hedges_to_btc4h_gld_qqq`

Allocation change versus baseline:

| Sleeve | Baseline | Candidate |
|---|---:|---:|
| BTC 1H trend | 10.0% | 0.0% |
| BTC 4H trend | 10.0% | 15.0% |
| ETH 1H trend | 10.0% | 10.0% |
| ETH 4H trend | 10.0% | 10.0% |
| BTC hedge | 5.0% | 0.0% |
| ETH hedge | 5.0% | 0.0% |
| SPY | 17.5% | 17.5% |
| QQQ | 17.5% | 27.5% |
| GLD | 15.0% | 20.0% |

Plain-English thesis:

> Remove noisy / expensive BTC 1H trend exposure and low-value hedge sleeves. Reallocate that capital into cleaner BTC 4H trend, QQQ compounding, and GLD ballast.

## Conservative fallback

Conservative fallback:

`candidate_btc1h_half_btc4h_half_qqq`

Allocation change versus baseline:

| Sleeve | Baseline | Candidate |
|---|---:|---:|
| BTC 1H trend | 10.0% | 0.0% |
| BTC 4H trend | 10.0% | 15.0% |
| ETH 1H trend | 10.0% | 10.0% |
| ETH 4H trend | 10.0% | 10.0% |
| BTC hedge | 5.0% | 5.0% |
| ETH hedge | 5.0% | 5.0% |
| SPY | 17.5% | 17.5% |
| QQQ | 17.5% | 22.5% |
| GLD | 15.0% | 15.0% |

This fallback keeps the hedge sleeves and produces smoother drawdown behavior, while still improving on the baseline.

## Cost profiles

| Profile | Crypto fee | Equity fee | Base slippage | Slippage volatility factor |
|---|---:|---:|---:|---:|
| default_1x | 0.0006 | 0.0001 | 3.0 | 50.0 |
| cost_1_5x | 0.0009 | 0.00015 | 4.5 | 75.0 |
| cost_2x | 0.0012 | 0.0002 | 6.0 | 100.0 |
| cost_3x | 0.0018 | 0.0003 | 9.0 | 150.0 |

## Results by cost profile

### Default costs

| Scenario | CAGR | Total return | MaxDD | Sharpe | Calmar | Final equity | 2022 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 18.51% | 177.01% | -17.88% | 1.223 | 1.035 | 277,005.29 | -8.65% | 5.02% |
| candidate_btc1h_hedges_to_btc4h_gld_qqq | 20.19% | 201.43% | -17.50% | 1.341 | 1.154 | 301,430.75 | -9.62% | 9.32% |
| candidate_btc1h_half_btc4h_half_qqq | 19.22% | 187.10% | -16.92% | 1.298 | 1.136 | 287,100.00 | -8.74% | 7.12% |

### 1.5x costs

| Scenario | CAGR | Total return | MaxDD | Sharpe | Calmar | Final equity | 2022 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 18.13% | 171.75% | -18.05% | 1.208 | 1.005 | 271,746.96 | -8.88% | 4.96% |
| candidate_btc1h_hedges_to_btc4h_gld_qqq | 19.88% | 196.70% | -17.59% | 1.328 | 1.130 | 296,698.49 | -9.76% | 9.27% |
| candidate_btc1h_half_btc4h_half_qqq | 18.88% | 182.20% | -17.07% | 1.284 | 1.106 | 282,201.16 | -8.95% | 7.03% |

### 2x costs

| Scenario | CAGR | Total return | MaxDD | Sharpe | Calmar | Final equity | 2022 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 17.77% | 166.72% | -18.20% | 1.193 | 0.976 | 266,719.16 | -9.09% | 4.93% |
| candidate_btc1h_hedges_to_btc4h_gld_qqq | 19.57% | 192.17% | -17.67% | 1.317 | 1.107 | 292,167.18 | -9.90% | 9.24% |
| candidate_btc1h_half_btc4h_half_qqq | 18.55% | 177.51% | -17.21% | 1.270 | 1.078 | 277,507.08 | -9.15% | 6.96% |

### 3x costs

| Scenario | CAGR | Total return | MaxDD | Sharpe | Calmar | Final equity | 2022 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 17.06% | 157.31% | -18.50% | 1.164 | 0.922 | 257,311.33 | -9.52% | 4.90% |
| candidate_btc1h_hedges_to_btc4h_gld_qqq | 18.98% | 183.67% | -17.83% | 1.294 | 1.064 | 283,669.00 | -10.17% | 9.20% |
| candidate_btc1h_half_btc4h_half_qqq | 17.91% | 168.69% | -17.47% | 1.244 | 1.025 | 268,694.73 | -9.54% | 6.86% |

## Candidate deltas versus same-tier baseline

### Leading candidate

| Cost profile | CAGR delta | MaxDD delta | Sharpe delta | Calmar delta | Final equity delta | 2022 delta | 2025 delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| default_1x | +1.68 pts | +0.38 pts better | +0.118 | +0.119 | +24,425.46 | -0.97 pts | +4.30 pts |
| cost_1_5x | +1.75 pts | +0.46 pts better | +0.120 | +0.125 | +24,951.53 | -0.88 pts | +4.31 pts |
| cost_2x | +1.80 pts | +0.53 pts better | +0.124 | +0.131 | +25,448.02 | -0.81 pts | +4.31 pts |
| cost_3x | +1.92 pts | +0.67 pts better | +0.130 | +0.142 | +26,357.67 | -0.65 pts | +4.30 pts |

### Conservative fallback

| Cost profile | CAGR delta | MaxDD delta | Sharpe delta | Calmar delta | Final equity delta | 2022 delta | 2025 delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| default_1x | +0.71 pts | +0.96 pts better | +0.075 | +0.101 | +10,094.71 | -0.09 pts | +2.10 pts |
| cost_1_5x | +0.75 pts | +0.98 pts better | +0.076 | +0.101 | +10,454.20 | -0.07 pts | +2.07 pts |
| cost_2x | +0.78 pts | +0.99 pts better | +0.077 | +0.102 | +10,787.92 | -0.06 pts | +2.03 pts |
| cost_3x | +0.85 pts | +1.03 pts better | +0.080 | +0.103 | +11,383.40 | -0.02 pts | +1.96 pts |

## Interpretation

The leading candidate passed every tested cost tier: default, 1.5x, 2x, and 3x.

At each tier, the leading candidate beat the same-tier baseline on:

- CAGR.
- Total return.
- Sharpe.
- Calmar.
- Final equity.
- Full-period max drawdown.

The conservative fallback also beat the same-tier baseline at every cost tier, with the best drawdown profile and nearly baseline-neutral 2022 performance.

The persistent caveat is that the leading candidate remains worse than baseline in 2022. However, this penalty did not widen under harsher cost assumptions. It narrowed from roughly 0.97 percentage points at default costs to roughly 0.65 percentage points at 3x costs.

The candidate hierarchy remained stable:

1. `candidate_btc1h_hedges_to_btc4h_gld_qqq` = leading allocation.
2. `candidate_btc1h_half_btc4h_half_qqq` = smoother fallback.
3. `baseline_40_35_15_10` = inferior under same-tier cost assumptions.

## Verdict

GREEN / PASSED.

The leading Core v1 candidate does not appear dependent on friendly execution assumptions. Its edge survives materially harsher fee and slippage settings, including the 2x serious robustness gate and the 3x stress / breakage probe.

No further cost-multiple escalation is needed for the main validation gate. The next recommended validation workstream is regime attribution and live signal readiness.
