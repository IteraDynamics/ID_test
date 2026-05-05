# Crypto Risk Budget v2 — Hybrid Direct Confirmation Results

## Status

**Research status:** direct hybrid confirmation complete.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** diagnostic only.

This document summarizes the direct hybrid finalist backtest confirmation for:

```text
hybrid_eth4h_cap75_only
hybrid_4h_cap75_1h_ecap75
full_ecap75_reference
full_cap75_reference
```

The direct confirmation reran sleeve-specific strategy assignments through the research harness rather than relying only on synthetic composition from existing sleeve equity curves.

## Stress-Cost Assumptions

```text
fee = 0.0008
base_slippage_bps = 5
slippage_vol_factor = 80
cooldown = 2
rebalance_threshold = 0.05
```

## Candidate Summary

| Candidate | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol | Worst 90D | Worst 180D | Max Time Underwater | Trades | Total Cost | Mapping |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| hybrid_eth4h_cap75_only | +383.28% | +26.00% | -21.66% | 1.407 | 1.200 | 17.52% | -14.74% | -17.67% | 772.33d | 1,222 | $692,818 | BTC_1H ecap75 / BTC_4H ecap75 / ETH_1H ecap75 / ETH_4H cap75 |
| hybrid_4h_cap75_1h_ecap75 | +430.53% | +27.73% | -23.48% | 1.420 | 1.181 | 18.43% | -15.00% | -19.00% | 772.42d | 1,260 | $782,015 | BTC_1H ecap75 / BTC_4H cap75 / ETH_1H ecap75 / ETH_4H cap75 |
| full_ecap75_reference | +308.86% | +22.94% | -20.94% | 1.379 | 1.096 | 15.90% | -14.18% | -16.56% | 772.38d | 1,167 | $540,895 | all sleeves ecap75 |
| full_cap75_reference | +465.33% | +28.93% | -26.66% | 1.361 | 1.085 | 20.16% | -16.07% | -22.29% | 773.79d | 1,394 | $872,389 | all sleeves cap75 |

## Target Frontier Candidates

The target filter was:

```text
CAGR >= 25%
MaxDD no worse than -35%
Sharpe >= 1.0
Calmar >= 0.9
```

Three direct candidates cleared the target frontier:

```text
hybrid_eth4h_cap75_only
hybrid_4h_cap75_1h_ecap75
full_cap75_reference
```

## Main Finding

The direct harness confirmation preserved the synthetic hybrid conclusion.

The two hybrid candidates sit on a better frontier than the pure references:

```text
hybrid_eth4h_cap75_only:
  Best Calmar and cleanest drawdown/return tradeoff.

hybrid_4h_cap75_1h_ecap75:
  Best Sharpe and higher growth than ETH4H-only hybrid.

full_cap75_reference:
  Highest return, but inferior Sharpe/Calmar and worst drawdown/stress profile.
```

## Candidate Interpretation

### 1. hybrid_eth4h_cap75_only — primary candidate

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
MaxDD:  -21.66%
Sharpe:  1.407
Calmar:  1.200
AnnVol: 17.52%
```

This is the cleanest direct-confirmed candidate. It improves materially over full ecap75 while preserving a controlled drawdown profile.

Compared with full ecap75:

```text
CAGR:       +3.05 percentage points
MaxDD:      -0.72 percentage points worse
Sharpe:     +0.028
Calmar:     +0.104
AnnVol:     +1.62 percentage points
Trades:     +55
Total Cost: +$151,923
```

Interpretation:

```text
This is the most efficient use of additional risk budget found so far.
```

### 2. hybrid_4h_cap75_1h_ecap75 — growth finalist

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
MaxDD:  -23.48%
Sharpe:  1.420
Calmar:  1.181
AnnVol: 18.43%
```

Compared with ETH4H-only hybrid:

```text
CAGR:       +1.74 percentage points
MaxDD:      -1.81 percentage points worse
Sharpe:     +0.013
Calmar:     -0.019
AnnVol:     +0.91 percentage points
Trades:     +38
Total Cost: +$89,198
```

Interpretation:

```text
This is a credible higher-growth candidate. It spends additional risk budget on BTC_4H and receives a meaningful CAGR increase, though Calmar declines slightly versus ETH4H-only.
```

### 3. full_cap75_reference — no longer preferred as the first promotion candidate

Performance:

```text
CAGR:   +28.93%
MaxDD:  -26.66%
Sharpe:  1.361
Calmar:  1.085
AnnVol: 20.16%
```

Interpretation:

```text
Full cap75 remains viable as an aggressive reference, but the hybrids preserve most of the upside with better risk-adjusted quality.
```

## Sleeve Summary Takeaway

The sleeve summary confirms the earlier attribution:

```text
ETH_4H cap75 is the most efficient upgrade.
BTC_4H cap75 adds growth but with additional drawdown budget.
ETH_1H cap75 remains unattractive and is excluded from both hybrid finalists.
BTC_1H remains controlled under ecap75 in both hybrids.
```

## Updated Candidate Classification

```text
Current baseline / conservative:
  trend_following_v8_ecap60_add80

Balanced finalist:
  trend_following_v8_ecap75

Primary Fund v2 candidate:
  hybrid_eth4h_cap75_only

Growth Fund v2 candidate:
  hybrid_4h_cap75_1h_ecap75

Aggressive reference, not preferred first:
  full_cap75_reference
```

## Decision

```text
No runtime changes approved.
No paper-trading changes approved.
No leverage approved.
Promote hybrid_eth4h_cap75_only to primary research finalist.
Keep hybrid_4h_cap75_1h_ecap75 as secondary growth finalist.
Do not promote full cap75 wholesale at this stage.
```

## Recommended Next Step

Before paper-trading promotion, complete a final comparison pack:

```text
1. Sortino calculation from candidate equity curves.
2. Year-by-year returns.
3. Passive BTC/ETH benchmark comparison.
4. Current Fund v1 baseline comparison.
5. Explicit paper-trading readiness checklist.
```

## Bottom Line

The direct hybrid confirmation is a major positive result.

Crypto Risk Budget v2 has found a direct-confirmed candidate that improves Fund v1 upside capture without broadly loosening all sleeves:

```text
BTC remains controlled.
ETH_4H receives the targeted risk-budget expansion.
ETH_1H stays controlled.
Full cap75 is avoided.
```

The strongest current candidate is:

```text
hybrid_eth4h_cap75_only
```
