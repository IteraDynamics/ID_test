# Itera Allocator v2 — Defensive Overlay Results

## Status

Research experiment complete. Allocator v2 is **not promoted** as the active Itera Fund allocator.

Allocator v2 was tested as a defensive overlay on top of the Itera Fund v0 static multi-asset baseline.

## Hypothesis

Allocator v1 attempted continuous relative-strength allocation and failed to improve the static baseline.

Allocator v2 tested a stricter defensive mandate:

```text
Default to the static baseline.
Intervene only when crypto risk deteriorates materially.
Otherwise do nothing.
```

The goal was not to maximize return. The goal was to determine whether rare defensive shifts could reduce drawdown and improve risk-adjusted performance versus static allocation.

## Design Summary

Allocator v2 used the following high-level behavior:

```text
Base allocation: 70% crypto / 30% equity
Defensive allocation: 50% crypto / 50% equity

Enter defensive mode when:
  crypto drawdown <= -10%
  and crypto trend score < 0

Remain defensive for at least 20 days.

Exit defensive mode when:
  crypto drawdown has recovered materially
  and crypto trend score turns positive
```

The backtest runner uses no-lookahead daily portfolio accounting:

```text
nav[t] = nav[t-1] * (1 + w_crypto[t-1] * r_crypto[t] + w_equity[t-1] * r_equity[t])
```

New weights are decided after the close using data through `t` and apply to the next day's returns.

## Test Window

```text
2019-03-08 → 2025-12-31
1715 daily bars
Initial capital: $100,000
```

## Results

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Allocator v2 | +151.27% | +14.47% | -13.15% | 1.278 | 1.100 | 11.08% |
| Static 70/30 | +174.56% | +15.97% | -14.02% | 1.347 | 1.139 | 11.51% |
| Static 60/40 | +161.18% | +15.12% | -13.10% | 1.405 | 1.154 | 10.43% |
| Static 50/50 | +147.94% | +14.25% | -12.25% | 1.446 | 1.163 | 9.55% |

## Delta vs Static 70/30

| Metric | Allocator v2 Delta |
|---|---:|
| CAGR | -1.50% |
| MaxDD | +0.86% |
| Sharpe | -0.069 |
| Calmar | -0.039 |

## Defensive Activity

| Metric | Value |
|---|---:|
| Average Crypto Weight | 66.3% |
| Defensive Days | 318 days / 18.5% |
| Weight Switches | 9 |
| Crypto 50% Weight Days | 317 |
| Crypto 70% Weight Days | 1398 |

## Verdict

Allocator v2 is **not promoted**.

It did reduce drawdown versus Static 70/30:

```text
Static 70/30 MaxDD: -14.02%
Allocator v2 MaxDD: -13.15%
Improvement: +0.86 percentage points
```

However, the drawdown improvement was not enough to justify the return and efficiency drag:

```text
CAGR:   -1.50 percentage points vs Static 70/30
Sharpe: -0.069 vs Static 70/30
Calmar: -0.039 vs Static 70/30
```

The key comparison is Static 60/40:

| Metric | Allocator v2 | Static 60/40 |
|---|---:|---:|
| CAGR | +14.47% | +15.12% |
| MaxDD | -13.15% | -13.10% |
| Sharpe | 1.278 | 1.405 |
| Calmar | 1.100 | 1.154 |

Static 60/40 outperformed Allocator v2 across every primary metric.

## Interpretation

Allocator v2 was directionally better than Allocator v1 in concept, but still failed the benchmark test.

The defensive overlay did something useful: it reduced crypto exposure during some adverse periods. But a simpler static allocation accomplished the same defensive objective more efficiently.

This suggests the current two-sleeve system does not yet need a dynamic allocator. Static capital policy remains superior.

## Decision

Allocator v2 should be archived as a rejected / not-promoted prototype.

It should not be used for:

- live trading
- paper trading
- Itera Fund v0 baseline replacement
- production allocator logic

## Current Baseline After Allocator v2

The active research baseline remains static allocation.

Recommended framing:

- **70/30** — flagship crypto-forward Itera Fund v0 baseline
- **60/40** — strongest balanced risk-adjusted candidate among current static allocations
- **50/50** — most stable high-Sharpe variant

## Research Lesson

The static frontier is strong enough that dynamic timing between only two sleeves is difficult to justify.

The next improvement is unlikely to come from another allocator that shifts between Crypto Sleeve v1 and Equity Sleeve v1. The better next research paths are:

1. improve Equity Sleeve v1 into Equity Sleeve v2;
2. improve Crypto Sleeve v1 / v2 after paper-trade validation;
3. add a third diversifying sleeve;
4. revisit dynamic allocation only after there are more sleeve inputs or stronger risk signals.

## Next Recommended Work

Stop allocator research for now.

The next highest-ROI work is to strengthen the sleeve universe before attempting allocator v3. The most logical next path is **Equity Sleeve v2**, because Equity Sleeve v1 is currently simple, defensive, and under-optimized as an equity sleeve.

The goal for Equity Sleeve v2 should not be curve-fit return maximization. It should be:

```text
Improve participation in equity recoveries and bull markets
while preserving Equity Sleeve v1's drawdown protection profile.
```

Potential Equity Sleeve v2 directions:

- volatility-adjusted exposure scaling;
- partial exposure instead of binary long/flat behavior;
- faster re-entry after crash conditions;
- equity regime classification;
- QQQ or SPY/QQQ dual-index sleeve comparison;
- simple risk-on/risk-off confirmation layer.

Allocator v2 is closed. Static Itera Fund v0 remains the control group.
