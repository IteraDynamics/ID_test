# Crypto Target Stream v1 — Findings

## Status

**Branch:** `research/crypto-target-stream-v1`

**Research status:** target-stream readiness audit and proxy generation completed.

**Decision:** promote Crypto Target Stream v1 as a successful proxy-readiness checkpoint.

**Runtime status:** no live trading, broker integration, paper-broker execution, runtime deployment, dashboard integration, or dynamic allocator changes approved.

## Executive Summary

Crypto Target Stream v1 successfully creates a lineage-aware crypto proxy target stream for the promoted Crypto Risk Budget v2 candidate:

```text
hybrid_eth4h_cap75_only

BTC_1H: ecap75
BTC_4H: ecap75
ETH_1H: ecap75
ETH_4H: cap75
```

The script found the richer component-level crypto artifact and generated a proxy target stream from component NAV/account values.

The generated stream is useful for fund-readiness, target-book integration, and future adapter development, but it is **not broker-ready** because it is inferred from realized component account values rather than intended strategy target weights.

Current readiness state:

```text
Component-level proxy stream: ready
Canonical intended target stream: not ready
Broker-paper execution: not ready
```

## Input Artifacts

Primary input:

```text
artifacts/fund_tilted_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
```

Fallback input:

```text
artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv
```

## Candidate Lineage

```text
candidate_name: hybrid_eth4h_cap75_only
btc_1h_config: ecap75
btc_4h_config: ecap75
eth_1h_config: ecap75
eth_4h_config: cap75
```

This lineage matters because the target stream should be associated with the promoted Crypto Risk Budget v2 candidate, not a generic historical crypto sleeve.

## Artifact Audit Result

### Primary artifact

The primary artifact loaded successfully:

```text
Path: artifacts/fund_tilted_cal_4s_2019-03-08_2025-12-31/equity_curves.csv
Status: component_nav_proxy_ready
Rows: 59,761
Start: 2019-03-08 00:00:00
End: 2025-12-31 00:00:00
Broker ready: false
```

Detected columns:

```text
portfolio
BTC_1H
BTC_4H
ETH_1H
ETH_4H
```

Detected component columns:

```text
BTC_1H
BTC_4H
ETH_1H
ETH_4H
```

Portfolio column:

```text
portfolio
```

Interpretation:

```text
The primary artifact contains portfolio and component NAV/account columns. It can support a component-NAV proxy stream, but it does not contain canonical intended target weights.
```

### Fallback artifact

The fallback artifact loaded successfully but was classified as curve-only:

```text
Path: artifacts/fund_side_by_side_composite_v1_tilted_4s/equity_curves.csv
Status: curve_only
Rows: 1,714
Start: 2019-03-08 00:00:00
End: 2025-12-30 00:00:00
Broker ready: false
```

It contains aggregate sleeve/fund curves such as:

```text
CRYPTO_SLEEVE
EQUITY_SLEEVE
FUND_STATIC_CRYPTO50_EQUITY50
FUND_STATIC_CRYPTO60_EQUITY40
FUND_STATIC_CRYPTO70_EQUITY30
FUND_STATIC_CRYPTO40_EQUITY60
FUND_STATIC_CRYPTO30_EQUITY70
SPY_HODL
QQQ_HODL
PASSIVE_SPY_QQQ_50_50
```

Interpretation:

```text
The fallback artifact is useful for fund composite reporting but does not contain crypto component weights or intended crypto targets.
```

## Generated Proxy Stream

Output location:

```text
artifacts/crypto_target_stream_v1/
```

Generated outputs:

```text
crypto_target_exposure.csv
crypto_target_schema.json
crypto_target_summary.csv
crypto_target_input_audit.csv
readiness_gaps.md
summary.md
summary.json
```

The generated proxy stream uses this method:

```text
btc_1h_target_weight = BTC_1H / portfolio
btc_4h_target_weight = BTC_4H / portfolio
eth_1h_target_weight = ETH_1H / portfolio
eth_4h_target_weight = ETH_4H / portfolio
crypto_cash_or_risk_off_weight = 1 - sum(component weights)
crypto_target_exposure = sum(component weights)
```

Because the source columns are component account values, the stream is labeled:

```text
source_status = proxy_from_component_nav
broker_ready = false
```

## Proxy Stream Summary

```text
Rows: 59,761
Start: 2019-03-08 00:00:00
End: 2025-12-31 00:00:00
Source status: proxy_from_component_nav
Broker ready: false
```

Average internal crypto sleeve proxy weights:

```text
BTC_1H: 31.28%
BTC_4H: 33.26%
ETH_1H: 21.70%
ETH_4H: 13.75%
Cash / risk-off: 0.00%
Crypto target exposure: 100.00%
```

Ranges:

```text
BTC_1H: 27.59% → 38.79%
BTC_4H: 24.25% → 37.87%
ETH_1H: 17.97% → 25.40%
ETH_4H: 11.28% → 17.36%
Crypto exposure: 100.00% → 100.00%
Cash / risk-off: 0.00% → 0.00%
```

Risk-state distribution:

```text
RISK_ON_PROXY: 100.00%
```

## Latest Target Row

Latest generated row:

```text
Timestamp: 2025-12-31
Candidate: hybrid_eth4h_cap75_only
Crypto target exposure: 100.00%
BTC_1H target weight: 31.24%
BTC_4H target weight: 35.26%
ETH_1H target weight: 20.39%
ETH_4H target weight: 13.11%
Crypto cash / risk-off weight: 0.00%
Crypto risk state: RISK_ON_PROXY
Source status: proxy_from_component_nav
Broker ready: false
```

## Interpretation

This is a meaningful improvement over the previous state.

Before Crypto Target Stream v1:

```text
Crypto sleeve was aggregate-curve ready only.
```

After Crypto Target Stream v1:

```text
Crypto sleeve has a component-level proxy allocation history tied to the promoted Crypto Risk Budget v2 candidate.
```

This supports future fund target-book integration because the proxy stream provides component-level weights for:

```text
BTC_1H
BTC_4H
ETH_1H
ETH_4H
```

However, the stream is still not a true intended target stream. It is inferred from realized component account values.

## Main Readiness Gap

The remaining gap is:

```text
Need canonical intended crypto target weights exported directly from promoted strategy logic.
```

A broker-paper-ready crypto target stream should be generated from intended strategy signals/allocations and should answer:

```text
What should the crypto sleeve hold at this timestamp?
```

not merely:

```text
What did each component account end up being worth at this timestamp?
```

## What v1 Proves

Crypto Target Stream v1 proves:

```text
1. The promoted candidate lineage can be encoded in the target stream artifact.
2. The primary crypto component artifact contains portfolio and component NAV/account columns.
3. A component-NAV proxy stream can be generated deterministically.
4. The proxy stream provides BTC_1H, BTC_4H, ETH_1H, and ETH_4H component weights.
5. The artifact is useful for fund-readiness and adapter development.
6. The artifact is not broker-ready and should not be treated as intended strategy targets.
```

## What v1 Does Not Prove

Crypto Target Stream v1 does not prove:

```text
true intended crypto target generation
broker-paper execution readiness
order generation correctness
fill simulation correctness
runtime deployment readiness
live trading readiness
strategy promotion beyond the documented research candidate
```

## Research Decision

Promote Crypto Target Stream v1 as a successful proxy-readiness checkpoint:

```text
The system can generate a lineage-aware component-NAV proxy stream for hybrid_eth4h_cap75_only, but broker-paper execution remains blocked until true intended crypto target weights are exported from strategy logic.
```

## Recommended Next Step

Next branch should be one of:

```text
research/crypto-signal-export-v1
research/crypto-target-contract-v2
```

Preferred next branch:

```text
research/crypto-signal-export-v1
```

Purpose:

```text
Export intended daily crypto target weights directly from the promoted Crypto Risk Budget v2 strategy logic.
```

Expected output shape:

```text
artifacts/crypto_signal_export_v1/
  crypto_intended_targets.csv
  crypto_signal_schema.json
  crypto_signal_summary.csv
  readiness_gaps.md
  summary.md
  summary.json
```

The intended target stream should eventually replace the current proxy stream as the broker-paper execution input.

## Guardrails

```text
No live trading.
No broker-paper execution.
No order generation.
No fills.
No runtime deployment.
No dashboard integration.
No new allocator logic.
No legal fund claim.
```

## Bottom Line

Crypto Target Stream v1 is successful.

It closes the gap from:

```text
aggregate crypto curve only
```

to:

```text
lineage-aware component-level crypto proxy target stream
```

But it also correctly preserves the next blocker:

```text
true intended crypto targets still need to be exported from strategy logic before broker-paper execution.
```
