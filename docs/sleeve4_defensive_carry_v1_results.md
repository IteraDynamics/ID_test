# Sleeve 4 Defensive Carry v1 — Research Results

## Status

**Research status:** first pass complete.

**Runtime status:** not approved for Fund v1 runtime integration.

**Promotion status:** not promoted as production allocation.

**Working role:** defensive benchmark / capital-preservation Sleeve 4 candidate.

This document summarizes the first Sleeve 4 Defensive Carry v1 experiment on branch:

```text
research/sleeve-4-search
```

The test compared the current three-sleeve core portfolio against static allocations that reserve 5–10% for a synthetic defensive carry sleeve.

## Objective

The purpose of this test was to determine whether a simple defensive carry sleeve improves the current core portfolio more effectively than chasing a fragile high-complexity fourth sleeve.

Current core:

```text
Crypto Sleeve v1  — primary return engine
SPY Equity v1     — defensive equity stabilizer
QQQ Growth v1b    — growth equity expression
```

Benchmark allocation:

```text
60% Crypto / 20% SPY / 20% QQQ / 0% Carry
```

Sleeve 4 candidate role:

```text
Defensive carry / capital preservation / dry powder
```

## Inputs

The test used the validated core equity curves:

```text
Crypto: artifacts/fund_equal_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
SPY:    artifacts/spy_trend_backtest/equity_curve.csv
QQQ:    artifacts/qqq_trend_v1/equity_curve.csv
```

Test period:

```text
2019-03-08 → 2025-12-31
1715 daily bars
```

The carry sleeve was synthetic in this first pass:

```text
Run 1: 0% annual carry / pure cash
Run 2: 4% annual carry / simple T-bill-style proxy
```

## Allocation Candidates Tested

```text
core_60_20_20           = 60% Crypto / 20% SPY / 20% QQQ / 0% Carry
carry_55_20_15_10       = 55% Crypto / 20% SPY / 15% QQQ / 10% Carry
carry_50_20_20_10       = 50% Crypto / 20% SPY / 20% QQQ / 10% Carry
carry_50_25_15_10       = 50% Crypto / 25% SPY / 15% QQQ / 10% Carry
carry_45_25_20_10       = 45% Crypto / 25% SPY / 20% QQQ / 10% Carry
carry_55_225_175_5      = 55% Crypto / 22.5% SPY / 17.5% QQQ / 5% Carry
```

## Pure Cash Result — 0% Carry

The pure-cash run did not improve the core portfolio enough to justify inclusion.

Core benchmark:

```text
core_60_20_20
Total Return: +166.10%
CAGR:         +15.44%
MaxDD:        -13.78%
Sharpe:        1.290
Calmar:        1.120
AnnVol:       11.68%
Worst 90D:    -10.26%
Worst 180D:   -12.26%
```

Best pure-cash risk-adjusted variant:

```text
carry_45_25_20_10
Total Return: +138.10%
CAGR:         +13.57%
MaxDD:        -12.32%
Sharpe:        1.307
Calmar:        1.102
AnnVol:       10.15%
Worst 90D:     -9.22%
Worst 180D:   -10.65%
```

Interpretation:

```text
Pure cash reduces volatility and drawdown, but gives up too much return.
It does not improve Calmar versus the 60/20/20 core.
```

Pure cash verdict:

```text
Reject as primary Sleeve 4 candidate.
Keep only as a zero-risk lower-bound benchmark.
```

## Synthetic 4% Carry Result

The 4% annual defensive-carry proxy produced a more coherent portfolio-shaping result.

Core benchmark:

```text
core_60_20_20
Total Return: +166.10%
CAGR:         +15.44%
MaxDD:        -13.78%
Sharpe:        1.290
Calmar:        1.120
AnnVol:       11.68%
Worst 90D:    -10.26%
Worst 180D:   -12.26%
```

Best Calmar / Sharpe candidate:

```text
carry_45_25_20_10
Total Return: +141.16%
CAGR:         +13.78%
MaxDD:        -12.04%
Sharpe:        1.334
Calmar:        1.145
AnnVol:       10.08%
Worst 90D:     -9.09%
Worst 180D:   -10.43%
```

Delta versus core:

```text
CAGR:   -1.65 percentage points
MaxDD:  +1.75 percentage points better
Sharpe: +0.044
Calmar: +0.025
AnnVol: -1.60 percentage points
```

Interpretation:

```text
A 4% defensive carry sleeve can modestly improve portfolio shape.
It is not a return enhancer.
It is a volatility/drawdown tradeoff sleeve.
```

## Crypto-Forward Variant

The strongest risk-adjusted result came from reducing crypto to 45%, but that may be less aligned with Itera's crypto-forward thesis.

The more philosophically aligned candidate is:

```text
carry_55_225_175_5
55% Crypto / 22.5% SPY / 17.5% QQQ / 5% Carry
```

Result:

```text
Total Return: +156.52%
CAGR:         +14.82%
MaxDD:        -13.22%
Sharpe:        1.304
Calmar:        1.121
AnnVol:       11.10%
Worst 90D:     -9.87%
Worst 180D:   -11.75%
```

Delta versus core:

```text
CAGR:   -0.62 percentage points
MaxDD:  +0.56 percentage points better
Sharpe: +0.013
Calmar: +0.001
AnnVol: -0.58 percentage points
```

Interpretation:

```text
The 5% carry variant modestly improves volatility and drawdown while preserving most of the crypto-forward profile.
It is not materially better than core, but it is a cleaner conservative variant than pure cash.
```

## Correlation Result

With synthetic 4% carry, the sleeve correlation profile was effectively orthogonal:

```text
Crypto vs Carry: +0.019
SPY vs Carry:    +0.002
QQQ vs Carry:    +0.004
```

This is expected for a smooth synthetic carry curve and should not be over-interpreted. A real T-bill ETF proxy may show small mark-to-market behavior and distribution effects.

## Research Interpretation

Defensive Carry v1 is not a high-alpha fourth sleeve.

It is a simple capital-preservation sleeve that creates a clear tradeoff:

```text
Lower CAGR
Lower volatility
Lower drawdown
Slightly improved Sharpe/Calmar at 4% carry
```

This makes it useful as a benchmark hurdle for future Sleeve 4 candidates.

Any future Sleeve 4 candidate should be compared against:

```text
1. 60/20/20 core baseline
2. 4% defensive carry benchmark
3. 5% crypto-forward carry variant
4. 10% risk-adjusted carry variant
```

## Decision

```text
Pure Cash Sleeve 4: rejected as primary candidate.
Synthetic 4% Carry Sleeve 4: keep as defensive benchmark / candidate.
Production promotion: no.
Runtime integration: no.
```

## Approved Next Step

The next required test is to replace synthetic carry with a real T-bill or short-duration proxy.

Suggested proxies:

```text
SGOV
BIL
SHV
Short-duration Treasury proxy if local data exists
```

The next test should answer:

```text
Does a real T-bill/short-duration proxy preserve the modest portfolio-shaping improvement seen with synthetic 4% carry?
Does distribution/price behavior create any unexpected artifacts?
Does the candidate remain useful after actual historical rates rather than a flat assumed 4%?
```

## Not Approved

This result does not approve:

```text
Fund v1 runtime changes
Paper-trading changes
Production allocation changes
Allocator integration
Execution changes
```

## Bottom Line

Defensive carry is not exciting, but it is useful as a research benchmark.

The first pass suggests that the current three-sleeve core is already strong. A defensive carry sleeve can modestly improve portfolio shape if it earns real yield, but it does not obviously transform the portfolio.

For now:

```text
Sleeve 4 Defensive Carry v1 remains alive as the benchmark fourth-sleeve hurdle.
Future Sleeve 4 candidates must beat both the 60/20/20 core and the defensive-carry benchmark without hidden tail risk.
```
