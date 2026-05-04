# Crypto Risk Budget v2 — Upside/Downside Capture Audit Results

## Status

**Research status:** first capture audit complete.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

**Decision status:** diagnostic only.

This document summarizes the first Crypto Risk Budget v2 capture audit comparing Fund v1 against passive BTC/ETH benchmarks.

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

## Performance Summary

| Series | Total Return | CAGR | MaxDD | Sharpe | Calmar | AnnVol |
|---|---:|---:|---:|---:|---:|---:|
| Fund v1 | +215.14% | +18.34% | -17.73% | 1.166 | 1.034 | 15.47% |
| BTC HODL | +2179.52% | +58.19% | -76.67% | 1.046 | 0.759 | 63.26% |
| ETH HODL | +2134.91% | +57.73% | -79.35% | 0.971 | 0.728 | 82.49% |
| BTC/ETH 50/50 Daily Rebalanced | +2627.71% | +62.41% | -76.34% | 1.053 | 0.818 | 69.48% |
| BTC/ETH 60/40 Daily Rebalanced | +2613.10% | +62.28% | -76.30% | 1.061 | 0.816 | 67.60% |

## Capture Summary

| Benchmark | Return Capture | Up-Day Capture | Down-Day Capture | 90D Bull Capture | 90D Bear Capture | Vol Ratio |
|---|---:|---:|---:|---:|---:|---:|
| BTC HODL | 10.03% | 19.93% | 18.63% | 20.94% | 10.38% | 24.46% |
| ETH HODL | 10.31% | 14.90% | 13.68% | 16.92% | 8.08% | 18.75% |
| BTC/ETH 50/50 Daily Rebalanced | 8.35% | 18.40% | 17.31% | 18.38% | 7.66% | 22.27% |
| BTC/ETH 60/40 Daily Rebalanced | 8.39% | 19.03% | 17.96% | 18.17% | 7.07% | 22.89% |

## Exposure / Beta Diagnostics

| Benchmark | Avg 90D Beta | Median 90D Beta | P10 90D Beta | P90 90D Beta |
|---|---:|---:|---:|---:|
| BTC HODL | 0.186 | 0.178 | 0.075 | 0.309 |
| ETH HODL | 0.141 | 0.131 | 0.059 | 0.246 |
| BTC/ETH 50/50 Daily Rebalanced | 0.176 | 0.169 | 0.071 | 0.308 |
| BTC/ETH 60/40 Daily Rebalanced | 0.181 | 0.176 | 0.073 | 0.314 |

## Interpretation

Fund v1 is not just moderately defensive. It is running at a very low realized crypto beta.

The audit shows:

```text
Fund v1 captures only ~8% to 10% of passive full-period crypto return.
Fund v1 captures only ~15% to 20% of up-day returns.
Fund v1 realizes only ~19% to 24% of benchmark volatility.
Fund v1's average rolling 90D beta is only ~0.14 to 0.19 depending on benchmark.
```

This explains the strategic discomfort that motivated the branch.

Fund v1 is excellent at reducing drawdown and volatility, but it may be underspending the available drawdown budget for a crypto-focused mandate.

## Main Finding

```text
Fund v1 is closer to a conservative systematic crypto allocation product than an aggressive institutional BTC/ETH sleeve.
```

This is not a failure. It is an important classification result.

## Research Implication

The next research step should not be more diversification or more defensive overlays.

The next step should test whether Fund v1 can increase upside capture while preserving a large drawdown advantage versus passive BTC/ETH.

Candidate levers:

```text
1. Exposure cap sweep.
2. Calibration threshold relaxation.
3. Sleeve weight sweep.
4. Trend-confirmed participation expansion.
5. Re-entry / recovery participation changes.
```

## Suggested Target Frontier

Current Fund v1 point:

```text
CAGR: ~18.34%
MaxDD: ~-17.73%
AnnVol: ~15.47%
```

Possible moderate-aggression target:

```text
CAGR: 25% to 30%
MaxDD: -22% to -28%
Sharpe: near or above 1.1
Calmar: near or above 1.0
```

Possible aggressive target:

```text
CAGR: 30% to 35%
MaxDD: -25% to -35%
Sharpe: near or above 1.0
Calmar: near or above 0.9
```

## Decision

```text
No runtime changes approved.
No paper-trading changes approved.
Fund v1 remains current paper-trading baseline.
Research should proceed to controlled risk-budget / upside-capture sweeps.
```

## Bottom Line

Fund v1 has proven that Itera can dramatically reduce passive crypto drawdown.

The open question is now whether Itera can intelligently spend some of that saved drawdown budget to buy back enough upside capture to make the crypto program more compelling as a flagship strategy.
