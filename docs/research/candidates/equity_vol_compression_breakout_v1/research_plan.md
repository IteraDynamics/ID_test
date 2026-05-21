# Equity Volatility Compression Breakout v1 — Research Plan

## Purpose

This candidate applies the first alpha-like structure found in crypto research to equity ETFs.

The research question:

```text
Do volatility-compression breakouts create positive expectancy in equity ETFs, especially growth/technology/semiconductor leadership assets?
```

## Candidate Classification

```text
Research lane: Equities
Candidate type: Volatility compression / breakout
Architecture role: Potential non-crypto Sleeve 2 alpha candidate
Status: NEW RESEARCH CANDIDATE
```

## Why This Path

The first-pass broad sector relative-strength test was mostly defensive allocation, not strong alpha.

The crypto volatility-compression breakout test was materially more alpha-like:

```text
low exposure
specific setup
positive trade expectancy
strong Calmar in first pass
```

This branch tests whether that same behavioral structure exists in equity ETFs.

## Initial Universe

Primary growth/technology set:

```text
QQQ
SMH
XLK
IGV
XLC
```

Optional broader comparison set:

```text
SPY
RSP
MTUM
QUAL
IWF
IWM
```

## First-Pass Strategy Physics

For each ETF independently:

```text
1. Compute rolling realized volatility.
2. Define compression when volatility is in a low percentile of recent realized volatility history.
3. Compute prior rolling channel high/low.
4. Enter long after compression when price breaks above the prior channel high.
5. Exit via channel-low break, trailing stop, or max holding period.
```

Initial side:

```text
long only
```

## Initial Variant Grid

Use a compact grid first:

```text
vol windows: 20d, 30d, 60d
vol rank windows: 90d, 180d
compression percentiles: 20%, 30%
channel windows: 20d, 30d, 40d
max hold days: 20, 40, 60
trailing stops: -10%, -15%, -20%
compression memory: 5d, 10d, 20d
```

## Benchmarks

Compare against:

```text
SPY buy-and-hold
QQQ buy-and-hold
RSP buy-and-hold
equal-weight tested universe
cash
```

## Required Metrics

```text
CAGR
Max drawdown
Sharpe
Calmar
final NAV
trade count
win rate
average trade return
median trade return
average hold days
exposure percentage
2020 crash return
2022 bear return
2023-2025 recovery/bull return
```

## Promotion Criteria

This candidate should only advance if it shows evidence of:

```text
positive expectancy per trade
reasonable trade count
better Calmar or Sharpe than SPY/QQQ
lower drawdown than buy-and-hold
not purely one ETF or one lucky trade
reasonable exposure and turnover
```

## Required Follow-Up If Promising

```text
mechanics audit
trade ledger attribution
subperiod validation
train/test split
rolling walk-forward
cost sensitivity
portfolio blend against Core crypto trend-following
```

## Initial Script Target

```text
scripts/run_equity_vol_compression_breakout.py
```

Expected outputs:

```text
artifacts/equity_vol_compression_breakout/results.csv
artifacts/equity_vol_compression_breakout/trades.csv
artifacts/equity_vol_compression_breakout/equity_curves.csv
artifacts/equity_vol_compression_breakout/summary.md
artifacts/equity_vol_compression_breakout/summary.json
```

## Boundary

```text
RESEARCH ONLY
NO RUNTIME WORK
NO BROKER WORK
NO LIVE PORTFOLIO INTEGRATION
```
