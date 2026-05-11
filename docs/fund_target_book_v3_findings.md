# Fund Target Book v3 — Findings

## Status

**Branch:** `research/fund-target-book-v3`

**Research status:** Unified daily fund target book completed.

**Decision:** promote v3 as a research-ready unified target-book checkpoint, not a broker-ready checkpoint.

**Runtime status:** no live trading, broker integration, paper-broker execution, order generation, fills, runtime deployment, dashboard integration, or dynamic allocator changes approved.

## Executive Summary

Fund Target Book v3 combines the two daily target streams produced by prior readiness work:

```text
Crypto Target Stream v1:
  artifacts/crypto_target_stream_v1/crypto_target_exposure_daily.csv

Fund Paper Readiness v2:
  artifacts/fund_paper_readiness_v2/equity_target_exposure.csv
```

It applies the current static fund structure:

```text
50% crypto sleeve
50% equity sleeve
```

and emits one unified daily fund-level instrument target book.

The result is research-ready and fully accounted, but not broker-ready.

Correct classification:

```text
fund_research_ready: true
fund_broker_ready: false
readiness_state: research_ready_crypto_proxy
```

## Input Alignment

Input alignment result:

```text
Crypto daily proxy rows: 2,491
Crypto date range: 2019-03-08 → 2025-12-31

Equity target rows: 1,714
Equity date range: 2019-03-08 → 2025-12-30

Aligned rows: 1,714
Aligned date range: 2019-03-08 → 2025-12-30
```

The final common panel correctly matches the equity daily target window.

## Readiness Summary

```text
Rows: 1,714
Start: 2019-03-08
End: 2025-12-30
Fund research ready: 100.00%
Fund broker ready: 0.00%
Accounting OK: 100.00%
Max absolute accounting error: 0.000000
Average total accounted weight: 100.00%
```

This confirms the unified daily target book accounts to 100% over the full aligned panel.

## Average Fund-Level Instrument Weights

With 50% crypto sleeve / 50% equity sleeve targets, the average total fund-level instrument weights were:

```text
BTC_1H: 15.64%
BTC_4H: 16.63%
ETH_1H: 10.85%
ETH_4H:  6.88%
Crypto cash/risk-off: 0.00%
SPY:    20.29%
QQQ:    20.23%
BIL:     9.48%
```

These weights correctly combine:

```text
crypto internal proxy weights × 50% fund crypto sleeve allocation
plus
equity internal target weights × 50% fund equity sleeve allocation
```

## Latest Unified Target Row

Latest row date:

```text
2025-12-30
```

Latest total fund target weights:

```text
Crypto sleeve: 50.00%
Equity sleeve: 50.00%

BTC_1H: 15.63%
BTC_4H: 17.63%
ETH_1H: 10.19%
ETH_4H:  6.55%
Crypto cash/risk-off: 0.00%

SPY: 25.00%
QQQ: 25.00%
BIL:  0.00%

Total accounted weight: 100.00%
Accounting error: 0.000000
```

Readiness state:

```text
research_ready_crypto_proxy
```

Readiness reason:

```text
Unified daily target book is research-ready, but broker_ready=false because crypto stream is proxy_from_component_nav and equity broker mapping is not approved.
```

## What v3 Proves

Fund Target Book v3 proves:

```text
1. The daily crypto proxy target stream can be aligned with the daily equity target stream.
2. Static 50/50 sleeve weights can be applied deterministically.
3. Crypto component proxy weights can be translated into total fund target weights.
4. Equity internal SPY/QQQ/BIL targets can be translated into total fund target weights.
5. The combined target book accounts to 100% over the full aligned panel.
6. Fund-level research readiness can be separated cleanly from broker readiness.
```

## What v3 Does Not Prove

Fund Target Book v3 does not prove:

```text
broker-paper execution readiness
order generation correctness
fill simulation correctness
symbol mapping correctness
cash handling correctness
market calendar handling correctness
runtime deployment readiness
live trading readiness
legal fund readiness
```

The largest remaining blocker is still:

```text
crypto target stream is proxy_from_component_nav, not intended strategy target output
```

## Research Decision

Promote v3 as:

```text
research-ready unified daily fund target book
```

Do not promote v3 as:

```text
broker-ready fund target book
```

Correct readiness classification:

```text
fund_target_book_research_ready = true
fund_target_book_broker_ready = false
```

## Recommended Next Step

Next branch should be:

```text
research/equity-alpha-lab-v1
```

Purpose:

```text
Start isolated equity alpha research without contaminating the current fund book.
```

A later branch should cover:

```text
research/fund-paper-execution-gap-v1
```

Purpose:

```text
Document the remaining bridge from research target book to paper-broker execution.
```

## Guardrails

```text
No live trading.
No broker integration.
No paper-broker execution.
No order generation.
No fills.
No runtime deployment.
No dashboard integration.
No dynamic allocator.
No legal fund claim.
```

## Bottom Line

Fund Target Book v3 is a major readiness artifact.

Itera now has:

```text
Equity daily target stream
Crypto daily proxy target stream
Unified daily fund instrument target book
100% target accounting over the aligned panel
Research-ready / broker-not-ready classification
```

This is the cleanest expression so far of the fund as a daily paper target book.

The next step is to start isolated equity alpha research while preserving the current fund book as the clean baseline.
