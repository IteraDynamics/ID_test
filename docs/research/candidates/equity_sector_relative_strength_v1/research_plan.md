# Equity Sector Relative Strength v1 — Research Plan

## Purpose

This branch returns to the original AI-fund/equity expansion objective.

The research question:

```text
Can Itera generate useful non-crypto alpha or active return by rotating across equity sectors based on relative strength?
```

## Candidate Classification

```text
Research lane: Equities
Candidate type: Sector relative-strength / sector rotation
Architecture role: Potential non-crypto Sleeve 2 candidate
Status: NEW RESEARCH CANDIDATE
```

## Why This Matters

Recent research produced useful crypto and defensive candidates, but the missing strategic lane remains non-crypto/equity expansion.

This candidate tests whether Itera can identify sector leadership inside equities instead of only improving crypto beta or defensive overlays.

## Initial Universe

Sector ETFs:

```text
XLK  Technology
XLF  Financials
XLE  Energy
XLV  Health Care
XLI  Industrials
XLY  Consumer Discretionary
XLP  Consumer Staples
XLU  Utilities
XLB  Materials
XLRE Real Estate
XLC  Communication Services
```

Benchmarks:

```text
SPY
QQQ
RSP
Equal-weight sector basket
```

## First-Pass Variants

Momentum lookbacks:

```text
63d
126d
252d
```

Selection styles:

```text
top1 sector
top3 equal-weight sectors
top5 equal-weight sectors
```

Risk gate:

```text
always on
SPY > SMA200
```

Risk-off destination:

```text
cash
```

## Required Metrics

```text
CAGR
Max drawdown
Sharpe
Calmar
final NAV
turnover/switch count
average holding days
sector exposure shares
crash-window return
bull-window return
```

## Correct Benchmarks

The primary comparison is not BTC or ETH.

Compare against:

```text
SPY buy-and-hold
QQQ buy-and-hold
RSP buy-and-hold
equal-weight sector basket
```

## Promotion Criteria

A candidate should only advance if it shows evidence of:

```text
better Sharpe or Calmar than SPY and equal-weight sector basket
reasonable turnover
not dependent on one sector or one period
survives subperiod and walk-forward checks
```

High CAGR alone is not enough.

## Initial Script Target

```text
scripts/run_equity_sector_relative_strength.py
```

Expected outputs:

```text
artifacts/equity_sector_relative_strength/results.csv
artifacts/equity_sector_relative_strength/equity_curves.csv
artifacts/equity_sector_relative_strength/exposure_summary.csv
artifacts/equity_sector_relative_strength/summary.md
artifacts/equity_sector_relative_strength/summary.json
```

## Boundary

```text
RESEARCH ONLY
NO RUNTIME WORK
NO BROKER WORK
NO LIVE PORTFOLIO INTEGRATION
```
