# Equity Enhancements v1 — Research Plan

## Status

**Branch:** `research/equity-enhancements-v1`

**Purpose:** Explore deeper equity research opportunities after Equity Book v1 established a clean SPY/QQQ SMA175 core.

**Guardrail:** This branch remains research-only. It does not approve paper trading, live allocation, broker/execution changes, runtime changes, dashboard changes, crypto allocator changes, or global crypto/equity allocator changes.

## Starting Point

The merged Equity Book v1 work established:

```text
Equity Core v1:
SPY_QQQ_50_50_SMA150_200_BAND
Preferred center: SMA175

Implementation-readiness module:
research/strategies/equity_spy_qqq_sma_band_v1.py
```

The current core profile from the signal-readiness replay was:

```text
SPY/QQQ SMA175 cash-risk-off:
  CAGR:   10.29%
  MaxDD: -19.56%
  Sharpe: 0.849
  Calmar: 0.526

Passive SPY/QQQ 50/50:
  CAGR:   12.93%
  MaxDD: -53.66%
  Sharpe: 0.712
  Calmar: 0.241
```

This is a strong core equity participation sleeve, but equities offer a larger research surface than SPY/QQQ timing alone.

## Equity Enhancements v1 Objective

The goal is to improve the Equity Core without immediately opening a broad overfit search across the entire equity universe.

The first enhancement family is:

```text
Defensive Carry / Risk-Off Substitute Sweep
```

Instead of changing the SPY/QQQ SMA175 signal, keep the equity signal fixed and vary only what inactive sleeves hold.

## Research Question

```text
Can we improve CAGR, Sharpe, Sortino, Calmar, and underwater behavior by replacing inactive SPY/QQQ sleeve cash with defensive ETFs, without materially worsening MaxDD or crisis-window behavior?
```

## First Sweep Universe

Base risk-off option:

```text
cash
```

Low-duration / cash-like defensive candidates:

```text
SGOV
BIL
SHV
```

Higher-risk defensive candidates:

```text
IEF
TLT
GLD
```

Interpretation guidance:

```text
SGOV/BIL/SHV:
  Expected to behave closest to cash-plus-yield.
  Preferred first candidates if they improve return without increasing drawdown much.

IEF/TLT:
  Duration-sensitive.
  May help in disinflationary crashes but can fail during rate shocks, especially 2022.

GLD:
  Crisis/inflation diversifier candidate.
  May help some regimes but is not a cash substitute.
```

## Method

Keep the Equity Core signal fixed:

```text
50% SPY sleeve:
  hold SPY when SPY close > SPY SMA175
  otherwise hold risk-off substitute

50% QQQ sleeve:
  hold QQQ when QQQ close > QQQ SMA175
  otherwise hold risk-off substitute
```

If both sleeves are risk-off, the book is 100% in the risk-off substitute.

For `cash`, inactive sleeve returns are 0.0.

For ETF substitutes, inactive sleeve returns are the selected defensive ETF's daily returns.

## Required Outputs

The sweep should produce:

```text
artifacts/equity_enhancements_v1_defensive_sweep/
  equity_curves.csv
  performance_summary.csv
  pairwise_cash_comparison.csv
  window_performance_summary.csv
  allocation_summary.csv
  skipped_assets.csv
  summary.json
  summary.md
```

## Evaluation Metrics

Primary metrics:

```text
CAGR
MaxDD
Sharpe
Sortino
Calmar
AnnVol
Worst 90d return
Worst 180d return
Max time underwater
```

Critical comparisons:

```text
1. Defensive substitute versus cash-risk-off over the same overlapping window.
2. Defensive substitute versus passive SPY/QQQ 50/50 over the same overlapping window.
3. Defensive substitute behavior during 2022 rate-shock/bear-market window.
```

## Named Windows

```text
FULL
GFC_2007_2009
COVID_2020
BEAR_2022
POST_2022_RECOVERY
RECENT_2025_PLUS
```

Some defensive ETF histories may start later than 2005. Each candidate must be evaluated over its own valid overlap, and comparisons against cash/passive must use the same candidate-specific overlap.

## Decision Rules

A defensive substitute is interesting only if it improves the core without hiding risk.

Prefer candidates that:

```text
1. Improve CAGR and/or Sharpe versus cash-risk-off over the same period.
2. Preserve or improve Calmar.
3. Do not materially worsen MaxDD.
4. Do not fail badly in 2022.
5. Remain simple and explainable.
```

Reject or demote candidates that:

```text
1. Improve full-period CAGR only because of duration tailwinds.
2. Worsen 2022 or rate-shock behavior materially.
3. Add equity-like drawdown during equity risk-off periods.
4. Require complex timing to justify.
```

## Non-Goals

```text
No paper trading.
No live trading.
No broker integration.
No dashboard integration.
No global crypto/equity allocator.
No sector rotation yet.
No factor rotation yet.
No volatility targeting yet.
No optimization across many parameters.
```

## Next Families After Defensive Carry

Only after defensive substitution is evaluated:

```text
1. Sector rotation sleeve.
2. Factor rotation sleeve.
3. Breadth/regime filters.
4. Volatility-managed equity exposure.
```

## Bottom Line

Equity Book v1 created a credible equity core. Equity Enhancements v1 starts by asking the cleanest next question: whether inactive SPY/QQQ sleeves should remain literal cash, or whether a simple defensive substitute improves the risk-adjusted return stream.
