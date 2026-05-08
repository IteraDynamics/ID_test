# Fund Paper Readiness v1 — Research Plan

## Status

**Branch:** `research/fund-paper-readiness-v1`

**Purpose:** Build the first paper-fund readiness layer for Itera's promoted two-sleeve architecture.

**Scope:** Ledger/accounting simulation only. This branch does not approve live trading, broker integration, paper-broker execution, dashboard integration, or dynamic crypto/equity allocation.

## Definition of "Fund" For This Branch

In this branch, "fund" means:

```text
A paper-accounted, multi-sleeve portfolio book that can track NAV, sleeve capital, target weights, realized weights, drift, rebalancing, returns, drawdowns, and performance over time.
```

It does not mean:

```text
Legal fund entity
LP/investor onboarding
Custody/admin/audit stack
Live broker execution
Production deployment
```

## Current Promoted Architecture

```text
Fund reporting view:
  50% crypto sleeve
  50% equity sleeve

Crypto sleeve:
  promoted independent systematic crypto engine candidate

Equity sleeve:
  SPY/QQQ SMA175 + BIL risk-off
```

This branch starts from the promoted side-by-side composite and makes the fund accounting explicit.

## Research Question

```text
Can Itera behave like a fund book in paper mode, even before broker integration?
```

More specifically:

```text
Can we produce a deterministic fund ledger that tracks daily NAV, sleeve NAV, target allocations, realized allocations, drift, rebalance events, drawdowns, and performance from existing promoted sleeve curves?
```

## Phase 1 — Static Sleeve Ledger

This branch implements Phase 1 only.

Inputs:

```text
artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv
```

Required columns:

```text
CRYPTO_SLEEVE
EQUITY_SLEEVE
```

Default target weights:

```text
50% crypto
50% equity
```

Optional target weights:

```text
60% crypto / 40% equity
40% crypto / 60% equity
```

The ledger should not use a dynamic allocator. Static target weights only.

## Method

1. Load sleeve equity curves.
2. Normalize each sleeve to the configured starting capital.
3. Convert sleeve equity curves to daily returns.
4. Simulate a fund book with static target weights.
5. Track actual sleeve capital after returns.
6. Trigger paper rebalance events when weight drift exceeds a configured threshold.
7. Move capital between sleeves in the ledger only; no broker orders are sent.
8. Record daily fund NAV, sleeve NAV, weights, drift, drawdown, and rebalance details.

## Default Parameters

```text
Initial capital: $100,000
Target weights: 50/50
Rebalance threshold: 5 percentage points absolute drift
Rebalance frequency: daily check
```

## Required Outputs

```text
artifacts/fund_paper_readiness_v1/
  fund_ledger.csv
  sleeve_nav.csv
  sleeve_weights.csv
  target_allocations.csv
  rebalance_events.csv
  performance_summary.csv
  drawdown_summary.csv
  summary.json
  summary.md
```

## Ledger Fields

The fund ledger should include at least:

```text
timestamp
fund_nav
fund_return
fund_drawdown
crypto_nav
equity_nav
crypto_target_weight
equity_target_weight
crypto_actual_weight
equity_actual_weight
crypto_drift
equity_drift
rebalance_needed
rebalance_executed
rebalance_amount_crypto
rebalance_amount_equity
```

## Promotion Criteria

This branch is successful if it can:

```text
1. Reproduce the static composite return stream within small tolerance.
2. Produce clear sleeve-level and fund-level NAV accounting.
3. Make rebalancing events explicit.
4. Produce readable summary artifacts.
5. Remain deterministic and research-only.
```

## Non-Goals

```text
No dynamic allocator.
No live trading.
No broker paper orders.
No exchange adapters.
No dashboard integration.
No legal fund setup.
No new alpha research.
```

## Future Phases

### Phase 2 — Signal-Driven Sleeve Paper Mode

```text
Each sleeve generates target exposure from strategy logic instead of reading precomputed sleeve curves.
```

### Phase 3 — Broker-Paper Integration

```text
Use broker abstractions and simulated orders/fills while preserving fund-level accounting.
```

### Phase 4 — Live-Readiness Review

```text
Fees, slippage, custody, calendars, failover, monitoring, kill switches, and operational controls.
```

## Bottom Line

This branch is the first step from research artifacts toward paper-trading like a fund. It does not trade, but it makes the fund book explicit.
