# BTC/ETH Relative Strength Research Plan

## Purpose

This research candidate tests whether a simple BTC/ETH relative-strength allocator can improve Itera's crypto sleeve versus static BTC/ETH exposure.

The goal is return-engine research, not defensive parking research.

## Core Question

```text
Can a deterministic BTC/ETH rotation improve risk-adjusted performance versus static BTC/ETH exposure?
```

## Benchmarks

Initial benchmarks:

```text
BTC buy and hold
ETH buy and hold
50/50 BTC/ETH static blend
60/40 BTC/ETH static blend
```

## First Test Variants

Momentum lookbacks:

```text
30d
60d
90d
180d
```

Allocation styles:

```text
leader_100:
  100% to the stronger asset

leader_75:
  75% stronger asset / 25% weaker asset
```

## Required Metrics

Each result should report:

```text
CAGR
Max drawdown
Sharpe
Calmar
final NAV
switch count
average holding days
BTC exposure percentage
ETH exposure percentage
```

## Validation Notes

This is first-pass research only. A strong full-sample result is not enough.

Required follow-up if promising:

```text
chronological subperiods
train/test split
rolling walk-forward
turnover/cost sensitivity
parameter stability review
```

## Initial Script Target

```text
scripts/run_btc_eth_relative_strength_research.py
```

Expected outputs:

```text
artifacts/btc_eth_relative_strength/results.csv
artifacts/btc_eth_relative_strength/equity_curves.csv
artifacts/btc_eth_relative_strength/summary.md
```

## Current Status

```text
NEW RESEARCH CANDIDATE
NO RUNTIME WORK
NO BROKER WORK
```
