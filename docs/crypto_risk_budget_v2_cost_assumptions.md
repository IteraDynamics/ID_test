# Crypto Risk Budget v2 — Cost Assumptions

## Status

**Research status:** active standard for Crypto Risk Budget v2.

**Runtime status:** no Fund v1 paper-trading or production changes approved.

This document records the default execution-cost assumptions for Crypto Risk Budget v2 research.

## Default Cost Model

Based on prior live trading experience through Coinbase Advanced, Crypto Risk Budget v2 research should use:

```text
Fee:      0.06% per side
Slippage: 3 bps per side
```

Equivalent notation:

```text
fee = 0.0006
base_slippage = 3 bps
```

Simple all-in estimate:

```text
9 bps per side
18 bps round trip
```

Where scripts support separate execution-model parameters, use:

```powershell
--fee 0.0006
--base-slippage 3
--slippage-vol-factor 50
--rebalance-threshold 0.05
```

The `slippage-vol-factor` value reflects the existing research harness pattern for volatility-sensitive slippage. It should remain consistent with prior Fund v1 / defensive-overlay research unless explicitly testing sensitivity.

## Why This Matters

Crypto Risk Budget v2 is exploring more aggressive participation. Any candidate that only works before realistic retail execution costs should be rejected.

The research hurdle is:

```text
Candidate variants must survive Coinbase Advanced-style costs before being considered valid.
```

## Guardrails

These assumptions are research defaults, not guarantees of future execution quality.

Before any runtime/paper-trading change, additional checks are required:

```text
1. Live order size versus book depth.
2. Actual Coinbase Advanced fee tier at the time of trading.
3. Maker/taker behavior.
4. Spread/slippage during high-volatility regimes.
5. Rebalance frequency and turnover.
6. Exchange/API outage behavior.
7. Financing/margin/liquidation modeling if leverage is ever considered.
```

## Current Decision

```text
Use fee=0.0006 and base_slippage=3 bps as default research assumptions.
Do not approve higher live exposure or leverage from these assumptions alone.
```
