# Fund Side-by-Side Composite v1 — Research Plan

## Status

**Branch:** `research/fund-side-by-side-composite-v1`

**Purpose:** Evaluate what Itera's fund-level performance would look like if independent crypto and equity systems ran side by side under static capital weights.

**Guardrail:** Research-only. This is not a return to a dynamic allocator. This branch does not approve live allocation, paper trading, broker/execution changes, runtime changes, dashboard changes, or global allocator changes.

## Why This Exists

Current architecture direction:

```text
Crypto systems run independently.
Equity systems run independently.
No single dynamic allocator decides which sleeve gets capital each bar.
```

However, an investor-facing fund view still needs to answer:

```text
If these systems were operated side by side, what would the total fund experience look like?
```

This is the difference between:

```text
Execution architecture:
  independent systems, no central allocator

Fund reporting / product view:
  static composite of independent sleeves
```

This research tests the second view only.

## Research Question

```text
What would fund-level performance look like if the crypto sleeve and equity sleeve ran side by side under static capital weights?
```

More specifically:

```text
Can a static crypto/equity composite deliver competitive total return while improving drawdown-adjusted metrics versus standalone crypto, standalone equities, and passive market benchmarks?
```

## Candidate Sleeve Inputs

### Crypto Sleeve

Input should be a pre-existing crypto sleeve equity curve artifact, for example:

```text
artifacts/crypto_risk_budget_v2_sweep/equity_curves.csv
artifacts/crypto_risk_budget_v2_capture_audit/equity_curves.csv
artifacts/fund_equal_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
```

The script should accept an explicit crypto column name, because crypto artifacts may contain multiple candidate curves.

### Equity Sleeve

Initial equity sleeve should be reconstructable from local market data:

```text
SPY/QQQ SMA175 with BIL risk-off
```

This reflects the merged Equity Core + Defensive Carry findings.

The script should also support reading an explicit equity curve CSV and column if needed.

## Static Composite Weights

Initial static weights:

```text
50% crypto / 50% equity
60% crypto / 40% equity
70% crypto / 30% equity
40% crypto / 60% equity
30% crypto / 70% equity
```

No dynamic allocator. No regime switching. No optimization.

## Method

1. Load crypto equity curve.
2. Load or compute equity sleeve equity curve.
3. Normalize both curves to 1.0 at common overlap start.
4. Convert each sleeve to daily returns.
5. Build static-weight rebalanced composites.
6. Compare against:

```text
crypto sleeve standalone
equity sleeve standalone
SPY_HODL
QQQ_HODL
SPY_QQQ_50_50
```

Optional if available:

```text
BTC_HODL
ETH_HODL
```

## Required Outputs

```text
artifacts/fund_side_by_side_composite_v1/
  equity_curves.csv
  performance_summary.csv
  capture_summary.csv
  window_performance_summary.csv
  input_summary.json
  summary.json
  summary.md
```

## Metrics

```text
Total return
CAGR
Max drawdown
Sharpe
Sortino
Calmar
Annualized volatility
Worst 90d return
Worst 180d return
Max time underwater
Return capture vs benchmarks
Up/down day capture vs benchmarks
```

## Named Windows

```text
FULL
COVID_2020
BEAR_2022
POST_2022_RECOVERY
RECENT_2025_PLUS
```

## Interpretation Rules

A composite is interesting if it:

```text
1. Preserves materially more return than pure equity.
2. Reduces drawdown versus pure crypto.
3. Improves Sharpe/Sortino/Calmar versus at least one standalone sleeve.
4. Has a cleaner investor ride than standalone crypto.
5. Does not rely on dynamic allocator assumptions.
```

A composite should not be called “market beating” unless the benchmark is clearly stated.

Preferred language:

```text
The side-by-side fund composite improved drawdown-adjusted return quality versus [benchmark] over [period], while preserving [x]% of the return profile.
```

## Non-Goals

```text
No dynamic allocator.
No paper trading.
No live trading.
No broker integration.
No capital-routing engine.
No optimizer.
No ML.
No dashboard integration.
```

## Bottom Line

This test answers a fund-performance question, not an execution-architecture question. It lets Itera evaluate whether independently run crypto and equity systems create a compelling combined fund return stream when viewed side by side.
