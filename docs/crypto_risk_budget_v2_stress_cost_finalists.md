# Crypto Risk Budget v2 — Stress-Cost Finalist Results

## Status

**Research status:** stress-cost finalist test complete.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** diagnostic only.

This document summarizes the finalist stress-cost test for:

```text
trend_following_v8_ecap75
trend_following_v8_cap75
```

## Stress-Cost Assumptions

This test used harsher legacy execution assumptions:

```text
fee = 0.0008
base_slippage_bps = 5
slippage_vol_factor = 80
cooldown = 2
rebalance_threshold = 0.05
```

These assumptions are more conservative than the Crypto Risk Budget v2 default Coinbase-style research assumptions:

```text
fee = 0.0006
base_slippage_bps = 3
slippage_vol_factor = 50
rebalance_threshold = 0.05
```

## Stress-Cost Results

| Strategy | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol | Worst 90D | Worst 180D | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| trend_following_v8_ecap75 | +308.86% | +22.94% | -20.94% | 1.379 | 1.096 | 15.90% | -14.18% | -16.56% | 1,167 |
| trend_following_v8_cap75 | +465.33% | +28.93% | -26.66% | 1.361 | 1.085 | 20.16% | -16.07% | -22.29% | 1,394 |

## Relative Comparison

Against ecap75 as baseline, cap75 produced:

```text
Total Return: +156.47 percentage points
CAGR:         +5.98 percentage points
MaxDD:        -5.72 percentage points worse
Sharpe:       -0.018
Calmar:       -0.011
AnnVol:       +4.26 percentage points
Trades:       +227
```

## Target Frontier

The target filter was:

```text
CAGR >= 25%
MaxDD no worse than -35%
Sharpe >= 1.0
Calmar >= 0.9
```

Only one finalist cleared the target-frontier filter under stress costs:

```text
trend_following_v8_cap75
```

Stress-cost frontier profile:

```text
CAGR:   +28.93%
MaxDD:  -26.66%
Sharpe:  1.361
Calmar:  1.085
AnnVol: 20.16%
Trades: 1,394
```

## Comparison to Default-Cost Finalist Results

### ecap75

Default-cost result:

```text
CAGR:   +23.98%
MaxDD:  -20.52%
Sharpe:  1.419
Calmar:  1.169
Trades: 1,194
```

Stress-cost result:

```text
CAGR:   +22.94%
MaxDD:  -20.94%
Sharpe:  1.379
Calmar:  1.096
Trades: 1,167
```

Interpretation:

```text
ecap75 survives stress costs with a modest degradation. It remains a strong balanced candidate, though its Calmar compresses from excellent to still-good.
```

### cap75

Default-cost result:

```text
CAGR:   +29.52%
MaxDD:  -26.64%
Sharpe:  1.381
Calmar:  1.108
Trades: 1,447
```

Stress-cost result:

```text
CAGR:   +28.93%
MaxDD:  -26.66%
Sharpe:  1.361
Calmar:  1.085
Trades: 1,394
```

Interpretation:

```text
cap75 survives stress costs remarkably well. It remains the only candidate that satisfies the aggressive crypto-fund target frontier.
```

## Main Finding

Both finalists are robust enough to remain active candidates under harsher execution assumptions.

The stress-cost test strengthens the case that the Crypto Risk Budget v2 opportunity is real:

```text
ecap75 = balanced upgrade candidate
cap75  = aggressive crypto-fund candidate
```

## Strategic Interpretation

The key result is that cap75 did not collapse under stress-cost assumptions.

This matters because the main concern with cap75 was that its higher turnover and higher exposure might be cost-fragile. The stress-cost run shows only modest degradation:

```text
Default-cost cap75 CAGR: +29.52%
Stress-cost cap75 CAGR:  +28.93%

Default-cost cap75 Calmar: 1.108
Stress-cost cap75 Calmar:  1.085
```

That keeps cap75 in finalist status.

## Current Candidate Classification

```text
Current conservative baseline:
  trend_following_v8_ecap60_add80

Balanced finalist:
  trend_following_v8_ecap75

Aggressive finalist:
  trend_following_v8_cap75
```

## Decision

```text
No runtime changes approved.
No paper-trading changes approved.
No leverage approved.
Keep both ecap75 and cap75 as finalists.
Proceed to sleeve-level attribution and contribution analysis.
```

## Next Required Check

The next research question is not whether finalists survive costs. They do.

The next question is:

```text
Where does the extra cap75 return and extra cap75 drawdown come from?
```

Required next analysis:

```text
BTC_1H vs BTC_4H vs ETH_1H vs ETH_4H contribution
sleeve-level CAGR / MaxDD / Sharpe / Calmar
sleeve-level trade counts
sleeve-level stress windows
whether cap75's edge is mostly ETH_1H turnover, BTC trend participation, or 4H structural exposure
```

## Bottom Line

The stress-cost test increases confidence in both finalists.

If the mandate is practical balanced improvement, ecap75 remains attractive.

If the mandate is a more fund-like aggressive crypto strategy, cap75 remains the only current finalist that reaches the desired frontier even under harsher costs.
