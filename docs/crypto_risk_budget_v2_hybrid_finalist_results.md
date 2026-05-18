# Crypto Risk Budget v2 — Hybrid Finalist Results

## Status

**Research status:** hybrid finalist composition complete.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** diagnostic only.

This document summarizes the hybrid finalist composition test using sleeve equity curves from the stress-cost finalist attribution run.

Input:

```text
artifacts/crypto_risk_budget_v2_finalist_sleeve_attribution/sleeve_equity_curves.csv
```

The hybrids are synthetic sleeve-equity compositions. They are useful for research triage but should be confirmed with a direct hybrid backtest/runtime implementation before promotion.

## Hybrid Summary

| Portfolio | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol | Worst 90D | Worst 180D | Max Time Underwater | Mapping |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| hybrid_eth4h_cap75_only | +384.37% | +26.04% | -21.46% | 1.433 | 1.214 | 17.19% | -14.60% | -17.44% | 539.83d | BTC_1H ecap75 / BTC_4H ecap75 / ETH_1H ecap75 / ETH_4H cap75 |
| hybrid_4h_cap75_1h_ecap75 | +431.80% | +27.78% | -23.09% | 1.445 | 1.203 | 18.11% | -14.86% | -18.77% | 772.33d | BTC_1H ecap75 / BTC_4H cap75 / ETH_1H ecap75 / ETH_4H cap75 |
| hybrid_all_cap75_except_eth1h | +453.98% | +28.55% | -24.83% | 1.435 | 1.150 | 18.73% | -15.03% | -20.56% | 773.17d | BTC_1H cap75 / BTC_4H cap75 / ETH_1H ecap75 / ETH_4H cap75 |
| full_ecap75_reference | +309.62% | +22.98% | -20.59% | 1.406 | 1.116 | 15.57% | -14.04% | -16.33% | 539.67d | all sleeves ecap75 |
| full_cap75_reference | +466.67% | +28.97% | -26.44% | 1.386 | 1.096 | 19.78% | -15.89% | -22.02% | 773.67d | all sleeves cap75 |
| hybrid_btc4h_cap75_only | +350.46% | +24.70% | -22.60% | 1.426 | 1.093 | 16.44% | -14.30% | -17.68% | 772.33d | BTC_1H ecap75 / BTC_4H cap75 / ETH_1H ecap75 / ETH_4H ecap75 |

## Target Frontier Candidates

The target filter was:

```text
CAGR >= 25%
MaxDD no worse than -35%
Sharpe >= 1.0
Calmar >= 0.9
```

Four rows cleared the target frontier:

```text
hybrid_eth4h_cap75_only
hybrid_4h_cap75_1h_ecap75
hybrid_all_cap75_except_eth1h
full_cap75_reference
```

## Main Finding

The hybrid tests found a better efficient frontier than either pure ecap75 or pure cap75.

Most important result:

```text
hybrid_eth4h_cap75_only
CAGR:   +26.04%
MaxDD:  -21.46%
Sharpe:  1.433
Calmar:  1.214
AnnVol: 17.19%
```

This is a major improvement over full ecap75 with only a small drawdown increase:

```text
Full ecap75:          22.98% CAGR / -20.59% MaxDD / 1.116 Calmar
ETH4H cap75 only:     26.04% CAGR / -21.46% MaxDD / 1.214 Calmar
```

The ETH4H-only hybrid adds more than three percentage points of CAGR while only worsening max drawdown by less than one percentage point and improving Sharpe/Calmar.

## Candidate Interpretation

### 1. hybrid_eth4h_cap75_only — Best balanced upgrade

Mapping:

```text
BTC_1H: ecap75
BTC_4H: ecap75
ETH_1H: ecap75
ETH_4H: cap75
```

This is the cleanest candidate so far.

It has:

```text
CAGR above 25%
MaxDD near -21.5%
Highest Calmar in the test
Strong Sharpe
Shorter underwater duration than 4H/full-cap variants
```

Interpretation:

```text
ETH_4H cap75 appears to be the most efficient use of extra risk budget.
```

### 2. hybrid_4h_cap75_1h_ecap75 — Best high-quality growth candidate

Mapping:

```text
BTC_1H: ecap75
BTC_4H: cap75
ETH_1H: ecap75
ETH_4H: cap75
```

Performance:

```text
CAGR:   +27.78%
MaxDD:  -23.09%
Sharpe:  1.445
Calmar:  1.203
```

This is also excellent. It adds more return than ETH4H-only while keeping Sharpe and Calmar strong.

Main drawback:

```text
Max time underwater rises to ~772 days, similar to full cap75.
```

Interpretation:

```text
4H-loosened is a credible aggressive-balanced candidate, but the longer underwater duration matters.
```

### 3. hybrid_all_cap75_except_eth1h — Higher return but less efficient

Mapping:

```text
BTC_1H: cap75
BTC_4H: cap75
ETH_1H: ecap75
ETH_4H: cap75
```

Performance:

```text
CAGR:   +28.55%
MaxDD:  -24.83%
Sharpe:  1.435
Calmar:  1.150
```

This improves materially over full cap75 by removing the weak ETH_1H cap75 component, but it is still less efficient than the ETH4H-only and 4H-cap hybrids.

### 4. full_cap75_reference — no longer preferred

Full cap75 remains valid, but the hybrid results make it less attractive.

Full cap75 has:

```text
Highest CAGR: +28.97%
Worst MaxDD: -26.44%
Lowest Sharpe among target candidates: 1.386
Lowest Calmar among target candidates: 1.096
Longest underwater duration: ~773.67 days
```

Interpretation:

```text
Full cap75 is now probably not the best promotion candidate. The hybrids keep most of the return benefit with better risk quality.
```

### 5. hybrid_btc4h_cap75_only — not preferred

This variant misses the 25% CAGR target:

```text
CAGR:   +24.70%
MaxDD:  -22.60%
Calmar:  1.093
```

Interpretation:

```text
BTC_4H cap75 alone helps, but not enough. ETH_4H cap75 is the more important sleeve change.
```

## Updated Candidate Classification

```text
Current conservative baseline:
  trend_following_v8_ecap60_add80

Balanced finalist:
  trend_following_v8_ecap75

Best hybrid balanced-upside candidate:
  hybrid_eth4h_cap75_only

Best hybrid growth candidate:
  hybrid_4h_cap75_1h_ecap75

Aggressive but no longer preferred as-is:
  full_cap75_reference
```

## Decision

```text
No runtime changes approved.
No paper-trading changes approved.
No leverage approved.
Do not promote full cap75 wholesale.
Proceed to direct hybrid implementation/backtest confirmation.
```

## Next Required Step

The hybrid composition was built from sleeve-level equity curves. Before any promotion, create or run a direct hybrid backtest implementation that explicitly assigns strategy variants by sleeve:

```text
BTC_1H: ecap75
BTC_4H: ecap75 or cap75
ETH_1H: ecap75
ETH_4H: cap75
```

Priority direct-confirmation candidates:

```text
1. hybrid_eth4h_cap75_only
2. hybrid_4h_cap75_1h_ecap75
```

## Bottom Line

Crypto Risk Budget v2 has found a better answer than simply increasing risk everywhere.

The best current insight is:

```text
Spend the extra risk budget selectively where it is most efficient — especially ETH_4H.
```

The branch should now move from synthetic hybrid composition to direct hybrid backtest confirmation.
