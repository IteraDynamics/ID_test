# Fund Paper Readiness v2 — Research Plan

## Status

**Branch:** `research/fund-paper-readiness-v2`

**Purpose:** Move Itera from curve-driven fund paper accounting toward signal-driven sleeve target generation.

**Scope:** Research-only target-generation readiness. This branch does not approve live trading, broker integration, paper-broker execution, dashboard integration, runtime deployment, or dynamic crypto/equity allocation.

## Background

Fund Paper Readiness v1 proved that Itera can represent the promoted two-sleeve architecture as a deterministic paper-accounted fund book.

v1 consumed precomputed sleeve equity curves:

```text
CRYPTO_SLEEVE
EQUITY_SLEEVE
```

and produced:

```text
fund NAV
sleeve NAVs
target weights
actual weights
drift
rebalance events
stress-window performance
correlation diagnostics
```

v2 moves one layer closer to actual paper trading by generating sleeve target exposures instead of only consuming sleeve equity curves.

## Definition of Success

v2 is successful if Itera can produce a deterministic daily target book for the promoted fund architecture:

```text
crypto sleeve target
combined fund target weights
readiness gaps for missing target streams
```

together with a fully generated equity sleeve target stream.

## Current Promoted Architecture

```text
Fund target view:
  50% crypto sleeve
  50% equity sleeve

Equity sleeve:
  SPY/QQQ SMA175 + BIL risk-off

Crypto sleeve:
  promoted independent systematic crypto engine candidate
```

## Key Design Constraint

Do not reintroduce a dynamic allocator.

v2 should not decide whether crypto or equity deserves more capital based on a live signal.

The fund-level capital split remains static:

```text
50% crypto
50% equity
```

The new work is inside the sleeves:

```text
Equity sleeve target generation
Crypto sleeve target input audit / adapter readiness
```

## Phase 2A — Equity Sleeve Target Generator

Generate daily equity sleeve target weights directly from market data:

```text
SPY target weight
QQQ target weight
BIL target weight
equity sleeve gross exposure
risk state / reason
```

Default rules:

```text
SPY above SMA175 => SPY target = 50% of equity sleeve
QQQ above SMA175 => QQQ target = 50% of equity sleeve
Any inactive sleeve capital goes to BIL
```

Examples:

```text
SPY above SMA175, QQQ above SMA175:
  SPY 50%, QQQ 50%, BIL 0%, gross equity exposure 100%

SPY above SMA175, QQQ below SMA175:
  SPY 50%, QQQ 0%, BIL 50%, gross equity exposure 50%

SPY below SMA175, QQQ below SMA175:
  SPY 0%, QQQ 0%, BIL 100%, gross equity exposure 0%
```

## Phase 2B — Crypto Target Adapter Readiness

Crypto target generation is likely less clean because the promoted crypto sleeve may currently exist as precomputed equity curves or strategy artifacts rather than a canonical daily target-exposure stream.

v2 should inspect the provided crypto input and classify it as one of:

```text
target_ready
curve_only
missing
invalid
```

If the crypto input is only an equity curve, v2 should explicitly document the gap:

```text
Need canonical crypto daily target exposure stream before broker-paper execution.
```

This is not a failure. It is a readiness finding.

## Phase 2C — Fund Target Book

Combine sleeve-level targets into a fund-level target book.

Default static fund weights:

```text
crypto sleeve capital target: 50%
equity sleeve capital target: 50%
```

For each day:

```text
fund_crypto_target_weight
fund_equity_target_weight
within_equity_spy_weight
within_equity_qqq_weight
within_equity_bil_weight
total_fund_spy_weight
total_fund_qqq_weight
total_fund_bil_weight
crypto_target_status
readiness_state
```

If crypto target exposure is missing, the fund target book should still emit the static sleeve target while flagging:

```text
crypto_target_status = curve_only / missing
readiness_state = partial
```

## Required Inputs

Default equity inputs:

```text
data/SPY_1D.csv
data/QQQ_1D.csv
data/BIL_1D.csv
```

Default crypto reference input:

```text
artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv
```

The crypto reference input should be used to audit whether a canonical daily target stream exists. It should not be treated as a broker-executable target stream unless it contains target/exposure columns.

## Required Outputs

```text
artifacts/fund_paper_readiness_v2/
  equity_target_exposure.csv
  crypto_target_input_audit.csv
  fund_target_book.csv
  sleeve_target_summary.csv
  readiness_gaps.md
  summary.json
  summary.md
```

## Promotion Criteria

This branch is successful if it:

```text
1. Generates a deterministic daily Equity Core target stream from SPY/QQQ/BIL data.
2. Builds a fund-level target book using static 50/50 sleeve targets.
3. Explicitly identifies whether the crypto sleeve is target-ready or only curve-ready.
4. Documents readiness gaps clearly.
5. Does not modify runtime or broker behavior.
```

## Non-Goals

```text
No live trading.
No broker paper execution.
No order generation.
No fills.
No dashboard integration.
No dynamic allocator.
No new alpha research.
No runtime deployment.
```

## Future Phase 3

Phase 3 should only happen after v2 if the target streams are clean.

Potential Phase 3:

```text
Fund Paper Execution Adapter v1
```

Purpose:

```text
Convert validated daily target weights into simulated paper orders/fills using existing broker abstractions, while preserving the v1 fund ledger accounting model.
```

## Bottom Line

v2 is not about improving historical performance.

v2 answers:

```text
Can Itera produce the daily target book needed to eventually paper-trade the fund structure?
```
