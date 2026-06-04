# Cross-Asset State Audit

## Status

Promotion branch: `gpt/promote-explicit-btc-state`.

This branch promotes explicit BTC macro-state from an additive diagnostic path into the canonical trend strategy and walk-forward runner path. It does not tune thresholds, change allocation weights, add ML, or add HMM logic.

## Ambiguity fixed

The previous `trend_following_v9` and `trend_following_v11` modules described BTC-specific concepts:

- BTC above SMA175 recovery confirmation
- BTC extension versus SMA365
- BTC parabolic exposure trim

But those modules computed those values from the local strategy dataframe. When the sleeve asset was ETH, the code could therefore use ETH-local SMA/extension while the docs described BTC state.

That ambiguity is now fixed by computing canonical BTC macro state once from BTC data and injecting it into every crypto trend sleeve before strategy evaluation.

## Canonical BTC state columns

The canonical helper is:

- `research/harness/cross_asset_state.py`

It computes these columns from BTC only:

- `btc_above_sma175`
- `btc_extension_sma365`
- `btc_parabolic_soft`
- `btc_parabolic_hard`
- `btc_parabolic_tier`

`trend_following_v9` consumes `btc_above_sma175`.

`trend_following_v11` consumes `btc_extension_sma365`.

## Canonical behavior

BTC sleeves:

- local BTC price action drives the base trend strategy
- BTC macro state is injected explicitly and should match BTC-local calculations after warmup

ETH sleeves:

- ETH price action drives the base trend strategy
- BTC macro recovery/parabolic state is injected explicitly
- metadata should report `explicit_btc`, not `asset_local_fallback`

The old fallback behavior remains only for backward compatibility. Any canonical research run that emits `asset_local_fallback` should be treated as non-canonical and inspected.

## Promoted files

- `research/harness/cross_asset_state.py`
  - canonical BTC macro-state computation and injection

- `scripts/cross_asset_state.py`
  - compatibility wrapper that imports from `research.harness.cross_asset_state`

- `research/strategies/trend_following_v9.py`
  - now explicitly consumes `btc_above_sma175` when present
  - records `btc_state_source`

- `research/strategies/trend_following_v11.py`
  - now explicitly consumes `btc_extension_sma365` when present
  - records `btc_parabolic_state_source`

- `scripts/run_multi_strategy_walkforward.py`
  - now computes/injects canonical BTC macro state
  - writes `cross_asset_state_audit.csv`

- `scripts/diagnose_explicit_btc_state.py`
  - lightweight diagnostic that confirms ETH trend strategies consume explicit BTC state

The prior additive runner `scripts/run_multi_strategy_walkforward_explicit_btc.py` remains available as a comparison harness.

## Validated A/B result

Same branch/data/weights/window were run against the original same-weight runner and the explicit-BTC runner.

Configuration:

- OOS window: 2021-01-01 to 2025-12-31
- trend weight: 0.40
- equity weight: 0.35
- gold weight: 0.15
- hedge weight: 0.10
- MR weight: 0.00
- initial capital: 100,000

Original same-weight runner:

```text
CAGR          12.66%
Total Return  81.45%
MaxDD        -18.68%
Sharpe         0.947
Calmar         0.678
2021         +29.00%
2022         -11.34%
2023         +27.87%
2024         +25.08%
2025          -2.02%
```

Explicit BTC-state runner:

```text
CAGR          14.17%
Total Return  93.91%
MaxDD        -17.80%
Sharpe         1.017
Calmar         0.796
2021         +24.90%
2022          -8.70%
2023         +28.94%
2024         +24.28%
2025          +4.80%
```

Audit result from the explicit run:

```text
50,734 audited trend rows
50,734 btc_state_source = explicit_btc
50,734 btc_parabolic_state_source = explicit_btc
0 asset_local_fallback
```

Per-sleeve audit coverage:

```text
BTC_1H_trend  16,580 explicit_btc
BTC_4H_trend   6,309 explicit_btc
ETH_1H_trend  20,502 explicit_btc
ETH_4H_trend   7,343 explicit_btc
```

## Interpretation

Explicit BTC anchoring reduced late-cycle/euphoric participation in 2021, improved 2022 bear behavior, preserved 2023 recovery, largely preserved 2024 upside, and materially improved 2025. This is treated as an architecture-correctness improvement, not a tuned performance optimization.

## Acceptance checks

Run the diagnostic:

```powershell
python scripts\diagnose_explicit_btc_state.py `
  --btc-data data\btcusd_3600s_2019-01-01_to_2025-12-30.csv `
  --eth-data data\ethusd_3600s_2019-01-01_to_2025-12-30.csv `
  --data-start 2019-01-01
```

Expected:

```text
v9_btc_state_source explicit_btc
v11_btc_parabolic_state_source explicit_btc
PASS explicit BTC state consumed by ETH trend strategies
```

Run the canonical walk-forward:

```powershell
python scripts\run_multi_strategy_walkforward.py `
  --btc-data data\btcusd_3600s_2019-01-01_to_2025-12-30.csv `
  --eth-data data\ethusd_3600s_2019-01-01_to_2025-12-30.csv `
  --spy-data data\SPY_1D.csv `
  --qqq-data data\QQQ_1D.csv `
  --bil-data data\BIL_1D.csv `
  --gld-data data\GLD_1D.csv `
  --trend-weight 0.40 `
  --equity-weight 0.35 `
  --gold-weight 0.15 `
  --hedge-weight 0.10 `
  --mr-weight 0.00 `
  --oos-start 2021-01-01 `
  --oos-end 2025-12-31 `
  --out-dir artifacts\wf_promoted_explicit_btc_state
```

Inspect audit sources:

```powershell
Import-Csv artifacts\wf_promoted_explicit_btc_state\cross_asset_state_audit.csv |
  Group-Object btc_state_source

Import-Csv artifacts\wf_promoted_explicit_btc_state\cross_asset_state_audit.csv |
  Group-Object btc_parabolic_state_source

Import-Csv artifacts\wf_promoted_explicit_btc_state\cross_asset_state_audit.csv |
  Group-Object sleeve,btc_state_source |
  Select-Object Count,Name
```

Canonical acceptance criterion:

- all trend audit rows show `explicit_btc`
- no trend audit rows show `asset_local_fallback`

## ML status

The recovery-trust ML gate remains a research/diagnostic negative result. It is not productionized by this branch.

## Research status

This branch promotes the explicit-BTC state fix as the new Core candidate baseline path. It is still research infrastructure, not production fund infrastructure.
