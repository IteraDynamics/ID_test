# Crypto Risk Budget v2 — Finalist Sleeve Attribution Results

## Status

**Research status:** finalist sleeve attribution complete.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** diagnostic only.

This document summarizes the sleeve-level attribution run comparing:

```text
trend_following_v8_ecap75
trend_following_v8_cap75
```

Baseline:

```text
trend_following_v8_ecap75
```

Stress-cost assumptions:

```text
fee = 0.0008
base_slippage_bps = 5
slippage_vol_factor = 80
cooldown = 2
rebalance_threshold = 0.05
```

## Portfolio Summary

| Strategy | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol | Trades | Total Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| trend_following_v8_ecap75 | +308.86% | +22.94% | -20.94% | 1.379 | 1.096 | 15.90% | 1,167 | $540,895 |
| trend_following_v8_cap75 | +465.33% | +28.93% | -26.66% | 1.361 | 1.085 | 20.16% | 1,394 | $872,389 |

Cap75 versus ecap75:

```text
CAGR:       +5.98 percentage points
MaxDD:      -5.72 percentage points worse
Sharpe:     -0.018
Calmar:     -0.011
AnnVol:     +4.26 percentage points
Trades:     +227
Total Cost: +$331,494
```

## Sleeve Summary

| Strategy | Sleeve | Total Return | CAGR | MaxDD | Sharpe | Calmar | Trades | Total Cost | Avg Exposure | Pct In Market |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cap75 | BTC_1H | +280.95% | +21.06% | -34.25% | 0.889 | 0.615 | 328 | $139,683 | 0.334 | 72.99% |
| ecap75 | BTC_1H | +232.92% | +18.75% | -30.16% | 0.914 | 0.622 | 296 | $102,270 | 0.290 | 72.99% |
| cap75 | BTC_4H | +789.97% | +36.67% | -38.78% | 1.284 | 0.946 | 228 | $242,748 | 0.332 | 54.40% |
| ecap75 | BTC_4H | +530.15% | +30.09% | -31.32% | 1.261 | 0.961 | 190 | $153,551 | 0.273 | 54.39% |
| cap75 | ETH_1H | +188.07% | +16.32% | -34.40% | 0.653 | 0.475 | 549 | $222,065 | 0.286 | 63.53% |
| ecap75 | ETH_1H | +185.10% | +16.15% | -33.61% | 0.750 | 0.481 | 447 | $169,104 | 0.232 | 63.52% |
| cap75 | ETH_4H | +402.26% | +25.94% | -33.74% | 0.894 | 0.769 | 289 | $267,893 | 0.270 | 44.31% |
| ecap75 | ETH_4H | +188.43% | +16.34% | -25.58% | 0.784 | 0.639 | 234 | $115,970 | 0.199 | 44.26% |

## Sleeve Delta: cap75 vs ecap75

| Sleeve | Delta CAGR | Delta MaxDD | Delta Sharpe | Delta Calmar | Delta Trades | Delta Cost | Delta Avg Exposure | Delta Pct In Market |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BTC_1H | +2.31 pts | -4.10 pts worse | -0.025 | -0.007 | +32 | +$37,413 | +0.044 | +0.00 pts |
| BTC_4H | +6.58 pts | -7.46 pts worse | +0.023 | -0.015 | +38 | +$89,198 | +0.059 | +0.01 pts |
| ETH_1H | +0.17 pts | -0.79 pts worse | -0.097 | -0.006 | +102 | +$52,961 | +0.055 | +0.01 pts |
| ETH_4H | +9.60 pts | -8.16 pts worse | +0.110 | +0.130 | +55 | +$151,923 | +0.071 | +0.05 pts |

## Main Findings

### 1. ETH_4H is the cleanest source of cap75 improvement

ETH_4H contributes the largest CAGR lift:

```text
Delta CAGR:   +9.60 percentage points
Delta Sharpe: +0.110
Delta Calmar: +0.130
```

This is the best-quality sleeve-level improvement. It pays for that with:

```text
Delta MaxDD:  -8.16 percentage points worse
Delta Cost:   +$151,923
Delta Trades: +55
```

Interpretation:

```text
ETH_4H appears to be the strongest evidence that cap75 is not just random extra risk. The extra exposure materially improves return and risk-adjusted quality at the sleeve level.
```

### 2. BTC_4H also contributes meaningfully, but with a Calmar penalty

BTC_4H adds:

```text
Delta CAGR:   +6.58 percentage points
Delta Sharpe: +0.023
Delta Calmar: -0.015
```

Interpretation:

```text
BTC_4H supports the cap75 thesis, but the extra drawdown offsets enough of the return gain that Calmar slightly declines versus ecap75.
```

### 3. BTC_1H is a modest return lift with slightly worse risk quality

BTC_1H adds:

```text
Delta CAGR:   +2.31 percentage points
Delta Sharpe: -0.025
Delta Calmar: -0.007
```

Interpretation:

```text
BTC_1H is not the reason to choose cap75. It adds some return, but the risk-adjusted trade is only marginal.
```

### 4. ETH_1H is the least attractive cap75 sleeve delta

ETH_1H adds almost no return:

```text
Delta CAGR:   +0.17 percentage points
Delta Sharpe: -0.097
Delta Calmar: -0.006
Delta Trades: +102
Delta Cost:   +$52,961
```

Interpretation:

```text
ETH_1H is the weakest part of cap75. It creates a lot of extra turnover and cost for almost no incremental CAGR.
```

## Strategic Interpretation

Cap75's extra portfolio return is not evenly distributed.

The strongest sources are:

```text
1. ETH_4H
2. BTC_4H
```

The weakest source is:

```text
ETH_1H
```

This suggests the next best research direction may not be a simple all-sleeves cap75 promotion.

A more precise candidate could be a hybrid:

```text
BTC_1H: ecap75 or conservative cap
BTC_4H: cap75 or loosened 4H cap
ETH_1H: ecap75 or conservative cap
ETH_4H: cap75
```

## Candidate Classification After Attribution

```text
trend_following_v8_ecap75:
  Balanced finalist. Clean, lower-turnover, practical improvement.

trend_following_v8_cap75:
  Aggressive finalist. Still valid, but extra edge appears concentrated in 4H sleeves, especially ETH_4H.

Hybrid 4H-loosened candidate:
  New recommended research candidate.
```

## Decision

```text
No runtime changes approved.
No paper-trading changes approved.
No leverage approved.
Do not blindly promote all-sleeves cap75 yet.
Proceed to test a hybrid candidate that applies cap75 behavior selectively to the sleeves where it adds the most value.
```

## Recommended Next Experiment

Test a hybrid allocation using existing strategy outputs if possible:

```text
BTC_1H: ecap75
BTC_4H: cap75
ETH_1H: ecap75
ETH_4H: cap75
```

Alternative variants:

```text
4H-only aggressive:
  BTC_1H ecap75 / BTC_4H cap75 / ETH_1H ecap75 / ETH_4H cap75

ETH4H-only aggressive:
  BTC_1H ecap75 / BTC_4H ecap75 / ETH_1H ecap75 / ETH_4H cap75

BTC4H+ETH4H aggressive with ETH1H suppressed:
  BTC_1H ecap75 / BTC_4H cap75 / ETH_1H ecap75 / ETH_4H cap75
```

## Bottom Line

The sleeve-level attribution materially improves the decision quality.

Cap75 is not just uniformly better. The strongest incremental edge is in 4H exposure, especially ETH_4H. ETH_1H cap75 is the weakest part of the aggressive candidate and likely should not be promoted without further testing.

The next research step should be a hybrid finalist test rather than choosing ecap75 or cap75 wholesale.
