# Crypto Risk Budget v2 — cap75 Candidate Review

## Status

**Research status:** cap75 candidate reviewed from per-strategy artifacts.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** diagnostic only.

This document reviews:

```text
trend_following_v8_cap75
```

as the first aggressive Crypto Risk Budget v2 finalist candidate.

## Cost Assumptions

The cap75 run used the Crypto Risk Budget v2 Coinbase-style execution-cost assumptions:

```text
fee = 0.0006
base_slippage_bps = 3.0
slippage_vol_factor = 50.0
rebalance_threshold = 0.05
```

## Headline Performance

```text
Total Return: +483.29%
CAGR:          +29.52%
MaxDD:         -26.64%
Sharpe:         1.381
Calmar:         1.108
AnnVol:        20.21%
Worst 90D:    -16.10%
Worst 180D:   -22.26%
Trades:         1,447
```

## Trade Counts

```text
BTC_1H: 334
BTC_4H: 243
ETH_1H: 565
ETH_4H: 305
Total:  1,447
```

Relative to ecap75, cap75 increases turnover materially, especially in ETH_1H and ETH_4H.

## Drawdown Path

The worst drawdown path in the uploaded equity curve was:

```text
Peak:     2019-06-26 18:00:00
Trough:   2020-01-03 01:00:00
Recovery: 2020-02-12 20:00:00
MaxDD:   -26.64%
P→T:      ~190 days
T→R:      ~40 days
```

The 2022 period also produces a major stress window, but the absolute max drawdown is the 2019-2020 episode in this cap75 artifact.

## Rolling Stress

```text
Worst 30D:  -13.28%
Worst 90D:  -16.10%
Worst 180D: -22.26%
Worst 365D: -25.84%
```

This is materially rougher than ecap75, especially on 180-day and 365-day stress windows.

## Yearly Returns

Approximate calendar-year returns from the cap75 equity curve:

```text
2020: +94.86%
2021: +61.45%
2022: -14.95%
2023: +36.46%
2024: +24.38%
2025:  -0.44%
```

Cap75 captures significantly more bull-market upside than ecap75, especially in 2020 and 2021.

## Comparison Versus ecap75

### cap75

```text
CAGR:   +29.52%
MaxDD:  -26.64%
Sharpe:  1.381
Calmar:  1.108
AnnVol: 20.21%
Trades: 1,447
```

### ecap75

```text
CAGR:   +23.98%
MaxDD:  -20.52%
Sharpe:  1.419
Calmar:  1.169
AnnVol: 16.06%
Trades: 1,194
```

### Difference

```text
CAGR:   cap75 +5.54 percentage points
MaxDD:  cap75 -6.12 percentage points worse
Sharpe: cap75 -0.038
Calmar: cap75 -0.061
AnnVol: cap75 +4.15 percentage points
Trades: cap75 +253
```

## Interpretation

Cap75 is the first implemented variant that reaches the desired aggressive crypto-risk frontier.

It is not a free lunch. It buys materially higher return by accepting:

```text
- worse max drawdown;
- worse 180D/365D stress windows;
- lower Sharpe and Calmar than ecap75;
- materially higher turnover;
- larger ETH-driven trade count load.
```

However, the absolute profile is still credible for a crypto-focused strategy:

```text
~29.5% CAGR
~-26.6% MaxDD
~1.38 Sharpe
~1.11 Calmar
```

This is much closer to the intended institutional crypto sleeve target than the current conservative Fund v1 baseline.

## Candidate Classification

```text
trend_following_v8_ecap60_add80:
  Conservative baseline / current Fund v1 family.

trend_following_v8_ecap75:
  Balanced finalist.

trend_following_v8_cap75:
  Aggressive finalist.
```

## Decision

```text
Keep cap75 as aggressive finalist.
Do not approve runtime or paper-trading changes.
Do not choose cap75 over ecap75 until stress-cost and robustness checks are complete.
```

## Required Next Checks

Before any promotion decision:

```text
1. Run stress-cost sensitivity on ecap75 and cap75:
   fee = 0.0008
   base_slippage_bps = 5
   slippage_vol_factor = 80
   cooldown = 2
   rebalance_threshold = 0.05

2. Run sleeve-level attribution:
   BTC_1H / BTC_4H / ETH_1H / ETH_4H contribution, drawdown, and turnover.

3. Check whether cap75's extra return comes mostly from ETH_1H/ETH_4H turnover.

4. Compare live-practicality:
   turnover, expected annual fees/slippage, and operational simplicity.

5. Evaluate whether there is a middle variant between ecap75 and cap75.
```

## Bottom Line

Cap75 is a legitimate aggressive finalist, but ecap75 remains the cleaner balanced candidate.

The real decision is not whether cap75 is good. It is whether the additional return is worth the higher drawdown, higher turnover, and rougher path versus ecap75.
