# Crypto Target Stream v1 — Research Plan

## Status

**Branch:** `research/crypto-target-stream-v1`

**Purpose:** Create or locate the canonical daily crypto target exposure stream required by Fund Paper Readiness v2.

**Scope:** Research-only target-stream readiness. This branch does not approve live trading, broker integration, paper-broker execution, runtime deployment, dashboard integration, or dynamic allocation.

## Background

Fund Paper Readiness v2 generated a daily Equity Core target stream from SPY/QQQ/BIL and built a static 50/50 fund target book.

v2 identified the remaining blocker:

```text
The crypto sleeve is curve-ready but not target-ready.
```

The promoted Crypto Risk Budget v2 candidate is:

```text
hybrid_eth4h_cap75_only

BTC_1H: ecap75
BTC_4H: ecap75
ETH_1H: ecap75
ETH_4H: cap75
```

This branch should orient the crypto target stream around that candidate, not a generic crypto sleeve.

## Research Question

```text
Can the promoted Crypto Risk Budget v2 candidate produce a canonical daily target exposure stream?
```

The target stream must answer:

```text
On each timestamp/day, what did the crypto sleeve intend to hold?
```

It should not merely answer:

```text
What was the realized crypto sleeve NAV?
```

## Required Target Stream Contract

Desired schema:

```text
timestamp
candidate_name
crypto_target_exposure
btc_1h_target_weight
btc_4h_target_weight
eth_1h_target_weight
eth_4h_target_weight
crypto_cash_or_risk_off_weight
crypto_risk_state
btc_1h_config
btc_4h_config
eth_1h_config
eth_4h_config
reason
source_strategy_version
source_status
broker_ready
```

Default lineage:

```text
candidate_name: hybrid_eth4h_cap75_only
btc_1h_config: ecap75
btc_4h_config: ecap75
eth_1h_config: ecap75
eth_4h_config: cap75
```

## Important Distinction

A component NAV/equity curve can be used to create a **proxy allocation history**, but that proxy is not the same as broker-executable intended target weights.

If only component curves exist, v1 may emit a proxy stream, but it must be labeled clearly:

```text
source_status = proxy_from_component_nav
broker_ready = false
```

## Expected Inputs

Primary candidate input:

```text
artifacts/fund_tilted_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
```

Expected possible component columns:

```text
portfolio
BTC_1H
BTC_4H
ETH_1H
ETH_4H
```

Fallback reference input:

```text
artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv
```

This fallback likely only contains aggregate sleeve curves and is expected to remain curve-only.

## Required Outputs

```text
artifacts/crypto_target_stream_v1/
  crypto_target_exposure.csv
  crypto_target_schema.json
  crypto_target_summary.csv
  crypto_target_input_audit.csv
  readiness_gaps.md
  summary.md
  summary.json
```

## Promotion Criteria

v1 is successful if it:

```text
1. Locates a true target-ready crypto artifact, OR
2. Builds a clearly labeled component-NAV proxy stream, OR
3. Clearly proves that only aggregate curves exist and documents the gap.
```

In all cases, v1 must distinguish:

```text
broker_ready = true
```

from:

```text
broker_ready = false
```

## Non-Goals

```text
No live trading.
No broker-paper execution.
No order generation.
No fills.
No runtime deployment.
No dashboard integration.
No new alpha research.
No dynamic allocator.
```

## Bottom Line

This branch exists to close the exact gap identified by Fund Paper Readiness v2:

```text
Equity side is target-ready.
Crypto side needs a canonical target exposure stream for hybrid_eth4h_cap75_only.
```
