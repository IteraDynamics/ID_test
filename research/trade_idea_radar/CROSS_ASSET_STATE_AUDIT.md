# Cross-Asset State Audit

## Status

Research hardening branch: `gpt/explicit-cross-asset-state-v2`.

This branch does not tune thresholds, change allocation weights, add ML, or add HMM logic. It adds an explicit-BTC walk-forward path so BTC macro state is auditable instead of inferred from whichever asset dataframe a strategy receives.

## Ambiguity fixed

The previous `trend_following_v9` and `trend_following_v11` modules described BTC-specific concepts:

- BTC above SMA175 recovery confirmation
- BTC extension versus SMA365
- BTC parabolic exposure trim

But those modules computed those values from the local strategy dataframe. When the sleeve asset was ETH, the code could therefore use ETH-local SMA/extension while the docs described BTC state.

## Canonical BTC state columns

The explicit-BTC runner computes these columns from BTC only:

- `btc_above_sma175`
- `btc_extension_sma365`
- `btc_parabolic_soft`
- `btc_parabolic_hard`
- `btc_parabolic_tier`

The runner injects these columns into every crypto trend sleeve before calling the explicit strategy variants.

## New files

- `scripts/cross_asset_state.py`
  - computes canonical BTC macro state
  - injects BTC state into sleeve dataframes

- `research/strategies/trend_following_v9_explicit_btc.py`
  - consumes `btc_above_sma175` when present
  - records `btc_state_source = explicit_btc`
  - falls back to asset-local SMA175 only when explicit BTC state is absent

- `research/strategies/trend_following_v11_explicit_btc.py`
  - consumes `btc_extension_sma365` when present
  - records `btc_parabolic_state_source = explicit_btc`
  - falls back to asset-local extension only when explicit BTC state is absent

- `scripts/run_multi_strategy_walkforward_explicit_btc.py`
  - walk-forward runner that uses the explicit BTC strategy variants for trend sleeves
  - writes `cross_asset_state_audit.csv`

- `scripts/diagnose_explicit_btc_state.py`
  - lightweight diagnostic that confirms ETH trend strategies consume explicit BTC state

## Expected behavior

BTC sleeves:

- local BTC price action still drives the base trend strategy
- BTC macro state is injected explicitly and should match BTC-local calculations after warmup

ETH sleeves:

- ETH price action still drives the base trend strategy
- BTC macro recovery/parabolic state is injected explicitly
- metadata should report `explicit_btc`, not `asset_local_fallback`

## Artifacts to inspect

After running the explicit walk-forward script, inspect:

- `cross_asset_state_audit.csv`
- `walkforward_explicit_btc_report.md`
- `stitched_oos_nav.csv`

For canonical runs, trend-sleeve audit rows should show:

- `btc_state_source = explicit_btc`
- `btc_parabolic_state_source = explicit_btc`

Any `asset_local_fallback` row means the strategy ran without canonical BTC macro-state columns and should be treated as non-canonical.

## ML status

The recovery-trust ML gate remains a research/diagnostic result only. It is not productionized by this branch.

## Research intent

This branch answers a correctness question:

> Did ETH and BTC trend sleeves consume the cross-asset BTC state we intended?

It does not answer whether the resulting performance is better. That must be evaluated by comparing the explicit-BTC walk-forward output against the prior Claude branch baseline.
