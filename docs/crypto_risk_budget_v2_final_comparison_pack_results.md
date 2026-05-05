# Crypto Risk Budget v2 — Final Comparison Pack Results

## Status

**Research status:** final comparison pack reviewed.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** research conclusion reached; implementation/paper-trading promotion still requires explicit approval.

This document summarizes the final comparison pack generated for Crypto Risk Budget v2.

Common comparison period:

```text
2019-03-08 00:00:00 → 2025-12-31 00:00:00
2491 bars
```

## Final Performance Summary

| Series | Total Return | CAGR | MaxDD | Sharpe | Sortino | Calmar | AnnVol | Worst 90D | Worst 180D | Max Time Underwater |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid_eth4h_cap75_only | +383.28% | +26.00% | -20.92% | 1.189 | 1.937 | 1.243 | 21.33% | -14.43% | -17.78% | 772d |
| hybrid_4h_cap75_1h_ecap75 | +430.53% | +27.73% | -23.01% | 1.202 | 1.961 | 1.205 | 22.46% | -14.66% | -19.09% | 772d |
| full_ecap75_reference | +308.86% | +22.94% | -20.49% | 1.170 | 1.898 | 1.120 | 19.23% | -13.88% | -16.68% | 772d |
| full_cap75_reference | +465.33% | +28.93% | -26.11% | 1.155 | 1.891 | 1.108 | 24.62% | -16.25% | -22.46% | 774d |
| Fund_v1_current | +214.90% | +18.32% | -17.57% | 1.158 | 1.864 | 1.043 | 15.58% | -10.33% | -13.70% | 773d |
| BTC/ETH 50/50 Daily Rebalanced | +2627.71% | +62.41% | -76.34% | 1.053 | 1.527 | 0.818 | 69.48% | -64.44% | -67.86% | 1098d |
| BTC HODL | +2179.52% | +58.19% | -76.67% | 1.046 | 1.551 | 0.759 | 63.26% | -58.60% | -60.75% | 846d |
| ETH HODL | +2134.91% | +57.73% | -79.35% | 0.971 | 1.434 | 0.728 | 82.49% | -69.75% | -74.82% | 1382d |

## Sortino Ranking

| Series | Sortino |
|---|---:|
| hybrid_4h_cap75_1h_ecap75 | 1.961 |
| hybrid_eth4h_cap75_only | 1.937 |
| full_ecap75_reference | 1.898 |
| full_cap75_reference | 1.891 |
| Fund_v1_current | 1.864 |
| BTC HODL | 1.551 |
| BTC/ETH 50/50 Daily Rebalanced | 1.527 |
| ETH HODL | 1.434 |

## Delta vs Current Fund v1

### hybrid_eth4h_cap75_only

```text
CAGR:       +7.67 percentage points
MaxDD:      -3.35 percentage points worse
Sharpe:     +0.031
Sortino:    +0.073
Calmar:     +0.200
AnnVol:     +5.76 percentage points
```

### hybrid_4h_cap75_1h_ecap75

```text
CAGR:       +9.41 percentage points
MaxDD:      -5.44 percentage points worse
Sharpe:     +0.044
Sortino:    +0.097
Calmar:     +0.163
AnnVol:     +6.89 percentage points
```

### full_cap75_reference

```text
CAGR:       +10.61 percentage points
MaxDD:      -8.53 percentage points worse
Sharpe:     -0.004
Sortino:    +0.027
Calmar:     +0.065
AnnVol:     +9.04 percentage points
```

## Benchmark Capture

Versus passive BTC/ETH benchmarks, the hybrids materially improve return capture versus current Fund v1 but remain far below passive crypto risk.

### Return capture vs BTC HODL

```text
Fund_v1_current:                10.08%
hybrid_eth4h_cap75_only:        17.97%
hybrid_4h_cap75_1h_ecap75:      20.19%
full_cap75_reference:           21.82%
```

### Vol ratio vs BTC HODL

```text
Fund_v1_current:                24.62%
hybrid_eth4h_cap75_only:        33.73%
hybrid_4h_cap75_1h_ecap75:      35.51%
full_cap75_reference:           38.91%
```

## Main Finding

The final pack confirms the Crypto Risk Budget v2 thesis:

```text
Fund v1 is too conservative for the intended crypto-fund mandate.
A selective hybrid risk-budget expansion improves return, Sortino, and Calmar while preserving a large drawdown advantage versus passive crypto.
```

## Candidate Interpretation

### 1. hybrid_eth4h_cap75_only — preferred primary candidate

Mapping:

```text
BTC_1H: ecap75
BTC_4H: ecap75
ETH_1H: ecap75
ETH_4H: cap75
```

Performance:

```text
CAGR:   +26.00%
MaxDD:  -20.92%
Sharpe:  1.189
Sortino: 1.937
Calmar:  1.243
AnnVol: 21.33%
```

This candidate offers the best Calmar, a strong Sortino, and the cleanest tradeoff versus current Fund v1. It adds more than 7.6 percentage points of CAGR versus current Fund v1 while worsening max drawdown by only about 3.35 percentage points.

Interpretation:

```text
Best primary Fund v2 candidate.
```

### 2. hybrid_4h_cap75_1h_ecap75 — higher-growth finalist

Mapping:

```text
BTC_1H: ecap75
BTC_4H: cap75
ETH_1H: ecap75
ETH_4H: cap75
```

Performance:

```text
CAGR:   +27.73%
MaxDD:  -23.01%
Sharpe:  1.202
Sortino: 1.961
Calmar:  1.205
AnnVol: 22.46%
```

This candidate has the highest Sharpe and Sortino among the strategy candidates, and materially higher CAGR than ETH4H-only. However, it spends more drawdown and volatility budget.

Interpretation:

```text
Best growth finalist, but slightly less clean than ETH4H-only on Calmar/drawdown efficiency.
```

### 3. full_cap75_reference — not preferred first

Performance:

```text
CAGR:   +28.93%
MaxDD:  -26.11%
Sharpe:  1.155
Sortino: 1.891
Calmar:  1.108
AnnVol: 24.62%
```

Full cap75 generates the highest CAGR, but it is less efficient and carries the weakest drawdown-adjusted profile among the finalists.

Interpretation:

```text
Aggressive reference, not preferred for initial promotion.
```

## Final Ranking

```text
1. hybrid_eth4h_cap75_only
   Preferred primary candidate.

2. hybrid_4h_cap75_1h_ecap75
   Strong secondary growth candidate.

3. full_ecap75_reference
   Balanced fallback.

4. full_cap75_reference
   Aggressive reference, not preferred first.

5. Fund_v1_current
   Current conservative baseline.
```

## Research Conclusion

The preferred next candidate is:

```text
hybrid_eth4h_cap75_only
```

because it improves the current Fund v1 profile from:

```text
Fund_v1_current:
CAGR:   +18.32%
MaxDD:  -17.57%
Sortino: 1.864
Calmar:  1.043
```

to:

```text
hybrid_eth4h_cap75_only:
CAGR:   +26.00%
MaxDD:  -20.92%
Sortino: 1.937
Calmar:  1.243
```

That is a high-quality risk-budget trade.

## Decision

```text
No runtime changes approved.
No paper-trading changes approved.
No leverage approved.
Research recommendation: promote hybrid_eth4h_cap75_only to implementation review as the primary Crypto Risk Budget v2 candidate.
Keep hybrid_4h_cap75_1h_ecap75 as the secondary growth candidate.
Do not promote full cap75 wholesale.
```

## Next Step

Proceed to implementation planning for a paper-trading candidate config, but only after explicit approval.

Implementation scope should be narrow:

```text
BTC_1H: ecap75
BTC_4H: ecap75
ETH_1H: ecap75
ETH_4H: cap75
```

No other strategy, allocator, execution, broker, or leverage changes should be included in the first implementation review.
