# Fund Target Book v3 — Research Plan

## Status

**Branch:** `research/fund-target-book-v3`

**Purpose:** Combine the daily equity target stream and daily crypto proxy target stream into one unified fund-level instrument target book.

**Scope:** Research-only target-book integration. This branch does not approve live trading, broker integration, paper-broker execution, order generation, fills, runtime deployment, dashboard integration, or dynamic allocation.

## Background

Fund Paper Readiness v2 produced a daily Equity Core target stream:

```text
artifacts/fund_paper_readiness_v2/equity_target_exposure.csv
```

Crypto Target Stream v1 produced a daily crypto proxy stream:

```text
artifacts/crypto_target_stream_v1/crypto_target_exposure_daily.csv
```

The crypto stream is explicitly:

```text
source_status = proxy_from_component_nav
broker_ready = false
```

This branch integrates those two daily streams into a single fund-level target book.

## Research Question

```text
Can Itera produce a unified daily fund target book that expresses total fund instrument weights across crypto components and equity instruments?
```

## Current Fund Structure

Static sleeve weights:

```text
crypto sleeve: 50%
equity sleeve: 50%
```

Crypto internal proxy components:

```text
BTC_1H
BTC_4H
ETH_1H
ETH_4H
crypto cash/risk-off
```

Equity internal components:

```text
SPY
QQQ
BIL
```

## Method

1. Load the daily crypto proxy target stream.
2. Load the daily equity target stream.
3. Align on common daily timestamps.
4. Apply static sleeve weights.
5. Convert internal sleeve weights into total fund instrument weights.
6. Emit a unified target book.
7. Mark research readiness and broker readiness separately.

## Required Inputs

```text
artifacts/crypto_target_stream_v1/crypto_target_exposure_daily.csv
artifacts/fund_paper_readiness_v2/equity_target_exposure.csv
```

## Required Outputs

```text
artifacts/fund_target_book_v3/
  fund_daily_target_book.csv
  fund_instrument_target_weights.csv
  fund_target_readiness_summary.csv
  input_alignment_audit.csv
  summary.md
  summary.json
```

## Required Columns — Fund Daily Target Book

```text
timestamp
fund_crypto_sleeve_weight
fund_equity_sleeve_weight
total_fund_btc_1h_weight
total_fund_btc_4h_weight
total_fund_eth_1h_weight
total_fund_eth_4h_weight
total_fund_crypto_cash_or_risk_off_weight
total_fund_spy_weight
total_fund_qqq_weight
total_fund_bil_weight
total_accounted_weight
crypto_source_status
crypto_broker_ready
equity_source_status
equity_broker_ready
fund_research_ready
fund_broker_ready
readiness_state
readiness_reason
```

## Expected Readiness Classification

Expected result:

```text
fund_research_ready = true
fund_broker_ready = false
```

Reason:

```text
The equity target stream is deterministic and target-ready for research.
The crypto target stream is daily and useful for research, but it is proxy_from_component_nav rather than intended strategy targets.
```

## Non-Goals

```text
No live trading.
No broker-paper execution.
No order generation.
No fills.
No runtime deployment.
No dashboard integration.
No dynamic allocator.
No new alpha research.
```

## Promotion Criteria

v3 is successful if it:

```text
1. Produces a unified daily fund target book.
2. Accounts total fund weights to approximately 100%.
3. Preserves crypto proxy readiness status.
4. Preserves equity target readiness status.
5. Emits clear readiness summary artifacts.
6. Does not imply broker readiness.
```

## Future Step

After v3, the next branch should likely be:

```text
research/equity-alpha-lab-v1
```

Purpose:

```text
Start isolated equity alpha research without contaminating the current fund book.
```

A second follow-up branch should eventually cover:

```text
research/fund-paper-execution-gap-v1
```

Purpose:

```text
Document the remaining bridge from research target book to paper-broker execution.
```

## Bottom Line

This branch should produce the first unified daily target book for the current Itera fund concept:

```text
crypto proxy targets + equity targets + static sleeve weights = total fund instrument targets
```

It is a major paper-readiness artifact, but it is still not broker-ready.
