# Sleeve 4 T-Bill / Short-Duration Proxy Results

## Status

**Research status:** first real-proxy pass complete.

**Runtime status:** not approved for Fund v1 runtime integration.

**Promotion status:** not promoted as production allocation.

This document summarizes the first real T-bill / short-duration proxy test for Sleeve 4 on branch:

```text
research/sleeve-4-search
```

The test replaced synthetic defensive carry with real Yahoo-adjusted ETF proxy data downloaded through:

```text
scripts/download_equity_data.py
```

## Objective

The previous synthetic carry test showed:

```text
Pure cash was not enough.
Synthetic 4% carry modestly improved portfolio shape.
```

The purpose of this pass was to test whether real T-bill / short-duration ETF proxies preserve that defensive-carry behavior.

## Core Benchmark

The benchmark remains the three-sleeve core:

```text
60% Crypto / 20% SPY / 20% QQQ / 0% Sleeve4
```

Core inputs:

```text
Crypto: artifacts/fund_equal_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
SPY:    artifacts/spy_trend_backtest/equity_curve.csv
QQQ:    artifacts/qqq_trend_v1/equity_curve.csv
```

## Proxies Tested

```text
SGOV — iShares 0-3 Month Treasury Bond ETF
BIL  — SPDR Bloomberg 1-3 Month T-Bill ETF
SHV  — iShares Short Treasury Bond ETF
SHY  — iShares 1-3 Year Treasury Bond ETF
VGSH — Vanguard Short-Term Treasury ETF
```

## Important Window Note

SGOV has a shorter available history in this test:

```text
SGOV overlap: 2020-06-01 → 2025-12-30, 1404 daily bars
```

The other proxies use the longer core overlap:

```text
BIL / SHV / SHY / VGSH overlap: 2019-03-08 → 2025-12-30, 1714 daily bars
```

Therefore, SGOV should not be compared directly to the longer-window BIL/SHV/SHY/VGSH results without considering the shorter test window.

## SGOV Result

SGOV was the only real proxy that clearly improved Calmar versus its overlap-window core benchmark.

Core benchmark over SGOV window:

```text
core_60_20_20
CAGR:   13.00%
MaxDD: -13.06%
Sharpe: 1.187
Calmar: 0.995
AnnVol: 10.81%
```

Best SGOV allocation:

```text
carry_45_25_20_10
45% Crypto / 25% SPY / 20% QQQ / 10% SGOV
CAGR:   11.88%
MaxDD: -11.32%
Sharpe: 1.242
Calmar: 1.050
AnnVol:  9.41%
```

Delta versus SGOV-window core:

```text
CAGR:   -1.11 percentage points
MaxDD:  +1.75 percentage points better
Sharpe: +0.055
Calmar: +0.055
AnnVol: -1.39 percentage points
```

Crypto-forward SGOV variant:

```text
carry_55_225_175_5
55% Crypto / 22.5% SPY / 17.5% QQQ / 5% SGOV
CAGR:   12.52%
MaxDD: -12.50%
Sharpe: 1.207
Calmar: 1.001
AnnVol: 10.23%
```

Interpretation:

```text
SGOV behaves like the cleanest real defensive-carry candidate so far, but the result depends on a shorter window beginning in 2020.
```

## BIL Result

BIL did not beat the longer-window core by Calmar, though it improved drawdown and Sharpe in some variants.

Core benchmark:

```text
core_60_20_20
CAGR:   15.48%
MaxDD: -13.78%
Sharpe: 1.294
Calmar: 1.123
AnnVol: 11.68%
```

Best BIL risk-shaping allocation:

```text
carry_45_25_20_10
CAGR:   13.75%
MaxDD: -12.27%
Sharpe: 1.326
Calmar: 1.121
AnnVol: 10.13%
```

Delta versus core:

```text
CAGR:   -1.73 percentage points
MaxDD:  +1.51 percentage points better
Sharpe: +0.033
Calmar: -0.003
AnnVol: -1.56 percentage points
```

Interpretation:

```text
BIL improves risk shape but does not clear the Calmar hurdle versus the 60/20/20 core.
```

## SHV Result

SHV was similar to BIL but slightly weaker on Calmar.

Best SHV risk-shaping allocation:

```text
carry_45_25_20_10
CAGR:   13.76%
MaxDD: -12.29%
Sharpe: 1.327
Calmar: 1.119
AnnVol: 10.12%
```

Delta versus core:

```text
CAGR:   -1.73 percentage points
MaxDD:  +1.49 percentage points better
Sharpe: +0.033
Calmar: -0.004
AnnVol: -1.56 percentage points
```

Interpretation:

```text
SHV is a viable defensive benchmark proxy, but not a portfolio-improving fourth sleeve versus core on this test.
```

## SHY Result

SHY underperformed BIL/SHV from a portfolio-shaping perspective.

Best SHY crypto-forward conservative variant by ranking:

```text
carry_55_225_175_5
CAGR:   14.81%
MaxDD: -13.46%
Sharpe: 1.301
Calmar: 1.100
AnnVol: 11.12%
```

Interpretation:

```text
SHY introduces more duration behavior and does not improve Calmar versus core.
```

## VGSH Result

VGSH behaved similarly to SHY.

Best VGSH crypto-forward conservative variant by ranking:

```text
carry_55_225_175_5
CAGR:   14.81%
MaxDD: -13.46%
Sharpe: 1.302
Calmar: 1.100
AnnVol: 11.12%
```

Interpretation:

```text
VGSH is not materially better than SHY and does not clear the core benchmark.
```

## Proxy Ranking

### Best Real Proxy So Far

```text
SGOV
```

Reason:

```text
SGOV is the only proxy in this pass that improved Calmar meaningfully versus its overlap-window core benchmark.
```

Caveat:

```text
SGOV has shorter history, so the result may partly reflect the 2020-2025 overlap window.
```

### Best Longer-History Proxy

```text
BIL
```

Reason:

```text
BIL has the longer 2019-2025 overlap and behaves closest to a clean T-bill proxy, but it did not beat the 60/20/20 core by Calmar.
```

### Weaker Short-Duration Proxies

```text
SHY
VGSH
```

Reason:

```text
These add more duration-like behavior and did not improve portfolio-level results enough to justify preference over BIL/SHV.
```

## Research Interpretation

The real-proxy pass confirms the synthetic carry conclusion:

```text
Defensive carry is useful as a benchmark and stabilizer.
It is not an obvious return-enhancing fourth sleeve.
```

The strongest real-world defensive-carry role is not a 10% allocation that materially improves the fund. It is a conservative sleeve that can reduce drawdown and volatility at the cost of lower CAGR.

## Decision

```text
SGOV: keep alive as best real defensive-carry candidate, subject to short-history caveat.
BIL: keep as longer-history benchmark / conservative fallback.
SHV: keep as secondary benchmark, not preferred.
SHY: reject as preferred Sleeve 4 proxy.
VGSH: reject as preferred Sleeve 4 proxy.
```

## Current Sleeve 4 Defensive Carry Verdict

```text
Do not promote to production allocation.
Keep SGOV/BIL as defensive-carry benchmarks.
Use these as hurdles for future Sleeve 4 candidates.
```

## Recommended Next Step

The next research step should not be runtime integration. It should be a focused overlap-window comparison:

```text
Compare SGOV, BIL, SHV, SHY, and VGSH on the same common window beginning 2020-06-01.
```

This will answer whether SGOV is genuinely better or simply benefiting from a shorter test window.

Required comparison:

```text
Same start/end date for all proxies.
Same core benchmark recomputed on that window.
Same allocations.
Ranking by Calmar, Sharpe, MaxDD, and worst rolling drawdown.
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

Real T-bill / short-duration proxies support the idea that Sleeve 4 Defensive Carry is a useful benchmark, but not a transformational sleeve.

SGOV is the best observed candidate so far, but because its history is shorter, it must be re-tested against the other proxies on a common 2020-2025 window before any final conclusion.
