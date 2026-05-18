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

The available crypto reference artifact contained NAV/equity curves such as:

```text
CRYPTO_SLEEVE
FUND_STATIC_CRYPTO50_EQUITY50
FUND_STATIC_CRYPTO60_EQUITY40
```

but did not contain intended daily target exposures.

## Research Question

```text
Can the promoted crypto sleeve produce a canonical daily target exposure stream?
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
crypto_target_exposure
btc_1h_target_weight
btc_4h_target_weight
eth_1h_target_weight
eth_4h_target_weight
crypto_cash_or_risk_off_weight
crypto_risk_state
reason
source_strategy_version
source_status
```

Definitions:

```text
crypto_target_exposure:
  total intended crypto risk exposure inside the crypto sleeve, from 0.0 to 1.0 or higher only if explicitly allowed.

btc_1h_target_weight / btc_4h_target_weight / eth_1h_target_weight / eth_4h_target_weight:
  internal target weights within the crypto sleeve.

crypto_cash_or_risk_off_weight:
  residual crypto sleeve allocation not deployed to active crypto strategy components.

crypto_risk_state:
  descriptive state such as RISK_ON, PARTIAL_RISK, RISK_OFF, CURVE_PROXY, or MISSING.

reason:
  human-readable explanation of target source.

source_strategy_version:
  strategy or artifact lineage.

source_status:
  target_ready, proxy_from_component_nav, curve_only, missing, or invalid.
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

## Phase 1 — Artifact Audit

Audit input files for:

```text
target-like columns
component NAV/equity columns
aggregate curve columns
missing or invalid schema
```

Classify each input as:

```text
target_ready
component_nav_proxy_ready
curve_only
missing
invalid
```

## Phase 2 — Proxy Target Stream If Possible

If component NAV columns exist:

```text
BTC_1H
BTC_4H
ETH_1H
ETH_4H
```

create a proxy target stream by normalizing component account values to portfolio value:

```text
btc_1h_proxy_weight = BTC_1H / portfolio
btc_4h_proxy_weight = BTC_4H / portfolio
eth_1h_proxy_weight = ETH_1H / portfolio
eth_4h_proxy_weight = ETH_4H / portfolio
cash_or_unallocated_proxy_weight = 1 - sum(component proxy weights)
```

This proxy is useful for readiness, reporting, and adapter development, but it is not broker-ready unless validated against intended strategy outputs.

## Phase 3 — Readiness Gap Documentation

If the source is only curve-ready or proxy-ready, document the remaining requirement:

```text
Need canonical intended crypto target weights from promoted crypto strategy logic.
```

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

## Future Step

If v1 produces a proxy stream only, the next step is:

```text
crypto-target-contract-v2 or crypto-signal-export-v1
```

Purpose:

```text
Export intended daily crypto target weights directly from promoted strategy logic.
```

## Bottom Line

This branch exists to close the exact gap identified by Fund Paper Readiness v2:

```text
Equity side is target-ready.
Crypto side needs a canonical target exposure stream.
```
