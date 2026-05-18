# Crypto Risk Budget v2 — Hypothetical Risk-Budget Sweep Results

## Status

**Research status:** first hypothetical risk-budget sweep complete.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** diagnostic only.

This document summarizes the first Crypto Risk Budget v2 risk-budget sweep. The test applied simple daily return multipliers to the existing Fund v1 equity curve to determine whether the current return stream can support a more aggressive crypto mandate.

## Important Guardrail

This was a what-if diagnostic only.

```text
Return multipliers above 1.0 are leverage-like diagnostics.
They are not approved runtime behavior.
They do not model financing, liquidation, margin, exchange limits, order-book impact, or live execution risk.
```

The goal was not to approve leverage. The goal was to test whether the Fund v1 return stream has enough quality that spending additional risk budget could move Itera toward a more compelling crypto-focused profile.

## Inputs

```text
Fund equity: artifacts/fund_equal_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
Fund column: portfolio
BTC data: data/btcusd_3600s_2019-01-01_to_2025-12-30.csv
ETH data: data/ethusd_3600s_2019-01-01_to_2025-12-30.csv
```

Common daily period:

```text
2019-03-08 00:00:00 → 2025-12-31 00:00:00
2491 daily bars
```

## Sweep Tested

```text
0.75x Fund v1 daily returns
1.00x Fund v1 daily returns
1.25x Fund v1 daily returns
1.50x Fund v1 daily returns
1.75x Fund v1 daily returns
2.00x Fund v1 daily returns
```

## Sweep Summary

| Candidate | Scale | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol | Worst 90D | Worst 180D | Return Capture vs BTC | Return Capture vs BTC/ETH 50/50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fund_v1_scale_0.75x | 0.75x | +140.15% | +13.71% | -13.53% | 1.166 | 1.013 | 11.60% | -8.06% | -10.40% | 6.54% | 5.44% |
| Fund_v1_scale_1.00x | 1.00x | +215.14% | +18.34% | -17.73% | 1.166 | 1.034 | 15.47% | -10.64% | -13.66% | 10.03% | 8.35% |
| Fund_v1_scale_1.25x | 1.25x | +309.40% | +22.97% | -21.79% | 1.166 | 1.054 | 19.34% | -13.16% | -16.83% | 14.41% | 12.00% |
| Fund_v1_scale_1.50x | 1.50x | +426.55% | +27.59% | -25.69% | 1.166 | 1.074 | 23.21% | -15.62% | -19.91% | 19.86% | 16.53% |
| Fund_v1_scale_1.75x | 1.75x | +570.47% | +32.20% | -29.44% | 1.166 | 1.093 | 27.07% | -18.03% | -22.89% | 26.54% | 22.09% |
| Fund_v1_scale_2.00x | 2.00x | +745.26% | +36.77% | -33.06% | 1.166 | 1.112 | 30.94% | -20.39% | -25.79% | 34.64% | 28.83% |

## Target Frontier Candidates

The initial target filter was:

```text
CAGR >= 25%
MaxDD no worse than -35%
Sharpe >= 1.0
Calmar >= 0.9
```

Three hypothetical rows cleared the target filter:

| Candidate | Scale | CAGR | MaxDD | Sharpe | Calmar | AnnVol | Return Capture vs BTC | Return Capture vs BTC/ETH 50/50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Fund_v1_scale_1.50x | 1.50x | +27.59% | -25.69% | 1.166 | 1.074 | 23.21% | 19.86% | 16.53% |
| Fund_v1_scale_1.75x | 1.75x | +32.20% | -29.44% | 1.166 | 1.093 | 27.07% | 26.54% | 22.09% |
| Fund_v1_scale_2.00x | 2.00x | +36.77% | -33.06% | 1.166 | 1.112 | 30.94% | 34.64% | 28.83% |

## Main Finding

The Fund v1 return stream scales cleanly in this first-order diagnostic.

Because this was a simple return multiplier, Sharpe remains mathematically stable across variants. The more interesting observation is that MaxDD and Calmar remain within a potentially acceptable crypto-risk budget even at 1.50x–2.00x hypothetical risk.

The sweep suggests:

```text
The core Fund v1 signal/return stream may be strong enough.
The current issue may be under-sizing / under-participation, not weak alpha.
```

## Strategic Interpretation

The previous capture audit showed that Fund v1 behaves like a very low-beta crypto strategy:

```text
~8% to 10% full-period return capture versus passive crypto
~15% to 20% up-day capture
~0.14 to 0.19 rolling 90D beta
```

This sweep shows that if the same return stream had been run with more risk budget, the profile begins to resemble a more compelling institutional crypto sleeve:

```text
1.50x: 27.6% CAGR / -25.7% MaxDD
1.75x: 32.2% CAGR / -29.4% MaxDD
2.00x: 36.8% CAGR / -33.1% MaxDD
```

That is much closer to the desired frontier:

```text
25% to 35% CAGR
-25% to -35% MaxDD
Sharpe >= 1.0
Calmar near or above 1.0
```

## Important Limitation

The sweep does not prove that live or research implementation can simply scale exposure.

Open issues before any promotion:

```text
1. Actual strategy internals may not scale linearly.
2. Higher exposure may change fills, slippage, costs, and rebalance behavior.
3. Some effective scaling may require leverage or margin, which is not approved.
4. Exchange and custody risk may grow nonlinearly.
5. Drawdowns under live stress may exceed backtest-scaled drawdowns.
6. Scaling a smoothed equity curve is not the same as changing underlying sleeve logic.
```

## Research Implication

The next step should be to test implementable, non-levered or minimally levered ways to increase participation from inside the crypto engine.

Candidate levers:

```text
1. Exposure cap relaxation.
2. Less conservative calibration thresholds.
3. Sleeve weight tilts toward higher-return sleeves.
4. Trend-confirmed participation expansion.
5. Re-entry / recovery participation improvements.
6. Max gross exposure sweep only if explicitly modeled as leverage-like and kept research-only.
```

## Decision

```text
No runtime changes approved.
No paper-trading changes approved.
No leverage approved.
Fund v1 remains current paper-trading baseline.
Proceed to implementable risk-budget levers in research only.
```

## Bottom Line

The first-order sweep strongly supports continuing Crypto Risk Budget v2 research.

Fund v1 appears to be conservative by sizing, not necessarily by signal weakness. The most promising next direction is to identify which real, implementable parameter changes can approximate the 1.50x–1.75x frontier without simply assuming leverage.
