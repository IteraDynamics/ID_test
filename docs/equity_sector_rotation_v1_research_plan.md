# Equity Sector Rotation v1 — Research Plan

## Status

**Branch:** `research/equity-sector-rotation-v1`

**Purpose:** Explore the first dedicated equity alpha sleeve after establishing Equity Core v1 and defensive carry research.

**Guardrail:** Research-only. This branch does not approve paper trading, live allocation, broker/execution changes, runtime changes, dashboard changes, crypto allocator changes, or global crypto/equity allocator changes.

## Context

Prior merged equity work established:

```text
Equity Core v1:
  SPY/QQQ SMA175 trend-risk book

Defensive Carry Enhancement:
  short-duration Treasury proxy risk-off family
  primary practical candidate: BIL
  best recent-history candidate: SGOV
  secondary practical candidate: SHV
```

Equity Sector Rotation v1 asks whether a separate equity alpha sleeve can improve risk-adjusted returns by rotating among major US sector ETFs.

## Research Question

```text
Can a simple sector momentum / trend-filtered rotation sleeve improve risk-adjusted returns versus passive SPY/QQQ, Equity Core SMA175 cash-risk-off, and Equity Core SMA175 defensive-carry variants?
```

## Universe

Initial liquid US sector ETF universe:

```text
XLK  Technology
XLV  Health Care
XLF  Financials
XLE  Energy
XLY  Consumer Discretionary
XLP  Consumer Staples
XLI  Industrials
XLU  Utilities
XLB  Materials
XLRE Real Estate
XLC  Communication Services
```

Known caveat:

```text
XLC and XLRE may have shorter histories than the older sector ETFs. The research script must skip missing/short-history assets cleanly and report valid overlap.
```

## Baseline Strategy Family

Initial strategy:

```text
Rank sectors by trailing momentum.
Hold top N sectors.
Require selected sectors to be above their own SMA trend filter.
Equal-weight selected sectors.
If no sectors qualify, hold risk-off asset.
```

Default parameters:

```text
Momentum lookback: 126 trading days
Trend filter:      200-day SMA
Top N:             3 sectors
Risk-off:          cash or BIL
Rebalance:         daily using closed-bar signal, effective next bar
```

## Variants To Test

Initial variants:

```text
1. SECTOR_TOP3_MOM126_SMA200_CASH
   Top 3 sectors by 126-day momentum, sector SMA200 filter, risk-off to cash.

2. SECTOR_TOP3_MOM126_SMA200_BIL
   Same, risk-off to BIL.

3. SECTOR_TOP3_MOM126_SMA200_SPYFILTER_CASH
   Same, but entire sleeve risk-off unless SPY > SPY SMA175.

4. SECTOR_TOP3_MOM126_SMA200_SPYFILTER_BIL
   Same, broad SPY filter with BIL risk-off.
```

The broad SPY filter is intended to test whether sector rotation should remain active during broad market downtrends or stand down with Equity Core.

## Benchmarks

Compare against:

```text
PASSIVE_SPY_QQQ_50_50
EQUITY_CORE_SMA175_CASH
EQUITY_CORE_SMA175_BIL, if BIL data exists
SPY_HODL
QQQ_HODL
```

## Required Outputs

The sweep should produce:

```text
artifacts/equity_sector_rotation_v1_sweep/
  equity_curves.csv
  performance_summary.csv
  window_performance_summary.csv
  allocation_summary.csv
  holdings_history.csv
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

Key questions:

```text
1. Does sector rotation improve Calmar versus Equity Core?
2. Does it improve Sharpe/Sortino without unacceptable MaxDD?
3. Does the SPY broad filter improve or suppress the strategy?
4. Does BIL risk-off improve the rotation sleeve versus cash?
5. Does the strategy rely on short-history sectors like XLC/XLRE?
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

## Decision Rules

Promote sector rotation only if it shows evidence of being a real equity alpha sleeve, not just noisier equity beta.

Prefer variants that:

```text
1. Improve Sharpe/Sortino/Calmar versus Equity Core and passive 50/50.
2. Avoid catastrophic MaxDD expansion.
3. Survive 2022 and other adverse windows.
4. Remain explainable: momentum + trend + equal-weight holdings.
5. Are not dependent on one short-history sector ETF.
```

Demote/reject variants that:

```text
1. Increase CAGR only by accepting much worse drawdown.
2. Depend heavily on XLC/XLRE short history.
3. Whipsaw badly in broad market stress.
4. Require complex parameter tuning to look attractive.
```

## Non-Goals

```text
No paper trading.
No live trading.
No broker integration.
No dashboard integration.
No global crypto/equity allocator.
No individual stock selection.
No options overlays.
No machine learning.
No optimization across dozens of parameter combinations yet.
```

## Bottom Line

Equity Sector Rotation v1 is the first test of whether Itera's equity work can move beyond a drawdown-controlled core and into a distinct, explainable equity alpha sleeve.
