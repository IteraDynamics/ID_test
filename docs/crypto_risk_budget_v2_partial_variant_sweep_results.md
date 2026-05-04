# Crypto Risk Budget v2 — Partial Strategy Variant Sweep Results

## Status

**Research status:** partial implementable strategy-variant sweep reviewed.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** diagnostic only.

This document summarizes the first partial calibrated v8-family strategy-variant sweep on branch:

```text
research/crypto-risk-budget-vtwo
```

The sweep uses the Crypto Risk Budget v2 Coinbase-style execution-cost assumptions:

```text
fee = 0.0006
base_slippage_bps = 3.0
slippage_vol_factor = 50.0
rebalance_threshold = 0.05
```

## Variants Reviewed

Completed variants in this snapshot:

```text
trend_following_v8_ecap75
trend_following_v8_ecap60_add80
trend_following_v8_cap75
trend_following_v8_ecap75_add90
trend_following_v8
```

Baseline for deltas:

```text
trend_following_v8_ecap60_add80
```

## Variant Summary

| Strategy | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol | Worst 90D | Worst 180D | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| trend_following_v8_ecap75 | +333.00% | +23.98% | -20.52% | 1.419 | 1.169 | 16.06% | -14.13% | -16.60% | 1,194 |
| trend_following_v8_ecap60_add80 | +223.54% | +18.80% | -16.82% | 1.409 | 1.118 | 12.81% | -11.66% | -13.52% | 1,146 |
| trend_following_v8_cap75 | +483.29% | +29.52% | -26.64% | 1.381 | 1.108 | 20.21% | -16.10% | -22.26% | 1,447 |
| trend_following_v8_ecap75_add90 | +235.15% | +19.41% | -18.01% | 1.417 | 1.078 | 13.13% | -12.84% | -14.22% | 1,038 |
| trend_following_v8 | +289.18% | +22.06% | -20.58% | 1.405 | 1.072 | 14.98% | -14.83% | -16.47% | 1,030 |

## Deltas Versus Baseline

### trend_following_v8_ecap75

```text
Total Return: +109.46 percentage points
CAGR:         +5.19 percentage points
MaxDD:        -3.70 percentage points worse
Sharpe:       +0.010
Calmar:       +0.051
AnnVol:       +3.26 percentage points
Trades:       +48
```

Interpretation:

```text
Cleanest balanced upgrade so far. It spends modest drawdown budget, materially improves CAGR, and improves both Sharpe and Calmar.
```

### trend_following_v8_cap75

```text
Total Return: +259.75 percentage points
CAGR:         +10.73 percentage points
MaxDD:        -9.82 percentage points worse
Sharpe:       -0.028
Calmar:       -0.009
AnnVol:       +7.41 percentage points
Trades:       +301
```

Interpretation:

```text
Only current target-frontier candidate. It reaches the desired crypto-fund return zone, but with meaningfully higher drawdown, higher volatility, and higher turnover.
```

### trend_following_v8_ecap75_add90

```text
Total Return: +11.61 percentage points
CAGR:         +0.62 percentage points
MaxDD:        -1.19 percentage points worse
Sharpe:       +0.008
Calmar:       -0.040
AnnVol:       +0.32 percentage points
Trades:       -108
```

Interpretation:

```text
Higher add-on cap alone does not solve the upside-capture problem. Not a preferred candidate.
```

### trend_following_v8

```text
Total Return: +65.64 percentage points
CAGR:         +3.26 percentage points
MaxDD:        -3.77 percentage points worse
Sharpe:       -0.004
Calmar:       -0.046
AnnVol:       +2.18 percentage points
Trades:       -116
```

Interpretation:

```text
Base v8 improves return versus baseline but worsens Calmar. It is less compelling than ecap75.
```

## Target Frontier Candidate

The target filter was:

```text
CAGR >= 25%
MaxDD no worse than -35%
Sharpe >= 1.0
Calmar >= 0.9
```

Only one variant cleared the target frontier filter:

```text
trend_following_v8_cap75
```

Performance:

```text
CAGR:   +29.52%
MaxDD:  -26.64%
Sharpe:  1.381
Calmar:  1.108
AnnVol: 20.21%
Trades: 1,447
```

## Main Findings

### 1. ecap75 is the best balanced candidate so far

```text
trend_following_v8_ecap75
```

This variant improves CAGR by more than five percentage points versus the current baseline while also improving Sharpe and Calmar. Its drawdown increase is meaningful but still moderate for a crypto-focused mandate.

### 2. cap75 is the best aggressive candidate so far

```text
trend_following_v8_cap75
```

This variant enters the target crypto-fund frontier zone. It is materially more aggressive and should be reviewed separately for path quality, drawdown duration, sleeve contribution, turnover, and stress-cost sensitivity.

### 3. add-on aggression is not enough

```text
trend_following_v8_ecap75_add90
```

The add-on-cap variant barely improves CAGR and reduces Calmar. This suggests the key lever is not simply allowing larger add-ons. The more important lever appears to be broader participation / cap structure.

### 4. base v8 is not preferred over ecap75

```text
trend_following_v8
```

Base v8 improves return but worsens Calmar relative to baseline and is inferior to ecap75 on the balanced mandate.

## Current Candidate Classification

```text
Conservative baseline:
  trend_following_v8_ecap60_add80

Balanced finalist:
  trend_following_v8_ecap75

Aggressive finalist:
  trend_following_v8_cap75

Not preferred:
  trend_following_v8_ecap75_add90
  trend_following_v8
```

## Decision

```text
No runtime changes approved.
No paper-trading changes approved.
No leverage approved.
Proceed to cap75-specific path review and sleeve-level attribution.
Keep ecap75 as the balanced finalist.
```

## Next Required Reviews

Before any promotion decision:

```text
1. Review cap75 full artifact set.
2. Compare ecap75 vs cap75 drawdown path and recovery behavior.
3. Inspect per-sleeve contribution and trade counts.
4. Run stress-cost sensitivity on finalists using legacy harsher assumptions:
   fee = 0.0008
   base_slippage_bps = 5
   slippage_vol_factor = 80
   cooldown = 2
   rebalance_threshold = 0.05
5. Confirm no candidate relies on one narrow calendar window.
```

## Bottom Line

This partial sweep strongly supports the Crypto Risk Budget v2 thesis:

```text
Fund v1 appears too conservative for the intended crypto-fund mandate.
Existing v8-family variants can spend additional drawdown budget in a controlled way.
```

The first real decision is now between:

```text
ecap75 — cleaner, balanced upgrade
cap75  — higher-return aggressive candidate
```
