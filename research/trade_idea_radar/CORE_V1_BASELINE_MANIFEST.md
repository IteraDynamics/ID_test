# Core v1 Candidate Baseline Manifest

Status: **BLESSED CANDIDATE**  
Branch: `gpt/promote-explicit-btc-state`  
Validation artifact directory: `artifacts/wf_promoted_full_2021_2025_workers`  
Validation date: 2026-06-04  

## Purpose

This manifest locks the first promoted Core candidate for the Itera Dynamics multi-sleeve research fund.

The defining architecture change is that all crypto trend sleeves consume **explicit BTC macro state** for recovery and parabolic gating. ETH trend sleeves must not derive BTC recovery/parabolic state from ETH-local prices.

## Canonical promoted files

- `research/harness/cross_asset_state.py`
- `scripts/cross_asset_state.py`
- `research/strategies/trend_following_v9.py`
- `research/strategies/trend_following_v11.py`
- `scripts/run_multi_strategy_walkforward.py`
- `scripts/diagnose_explicit_btc_state.py`

## Explicit BTC state columns

The canonical BTC macro-state helper provides:

```text
btc_above_sma175
btc_extension_sma365
btc_parabolic_soft
btc_parabolic_hard
btc_parabolic_tier
```

These columns are computed from BTC data only and forward-filled onto sleeve timestamps.

## Validated command

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
  --workers 5 `
  --out-dir artifacts\wf_promoted_full_2021_2025_workers
```

## Portfolio weights

```text
trend_weight   0.40
equity_weight  0.35
gold_weight    0.15
hedge_weight   0.10
mr_weight      0.00
```

## Validated stitched OOS performance

Window: `2021-01-01` to `2025-12-31`

```text
CAGR      14.17%
MaxDD    -17.80%
Sharpe     1.017
Calmar     0.796
```

Annual returns:

```text
2021     +24.90%
2022      -8.70%
2023     +28.94%
2024     +24.28%
2025      +4.80%
```

## Audit requirements

The full promoted run wrote `109,523` audited trend rows.

Required source counts:

```text
109,523 btc_state_source = explicit_btc
109,523 btc_parabolic_state_source = explicit_btc
0 asset_local_fallback
```

Validated sleeve coverage:

```text
BTC_1H_trend   43,801 explicit_btc
BTC_4H_trend   10,951 explicit_btc
ETH_1H_trend   43,816 explicit_btc
ETH_4H_trend   10,955 explicit_btc
```

## Promotion acceptance criteria

A future change regresses this baseline if any of the following are true:

1. ETH trend rows report `asset_local_fallback` for BTC recovery or parabolic state.
2. `cross_asset_state_audit.csv` is missing from the walk-forward artifacts.
3. The validated full-window command no longer reproduces materially similar stitched OOS metrics using the same data and costs.
4. The canonical trend strategy path no longer routes BTC state through `research/harness/cross_asset_state.py`.
5. Worker-enabled execution produces different results than sequential fold execution for the same config.

## Interpretation

This branch promotes explicit BTC macro-state ownership from additive experiment files into the canonical Core path. The validated improvement versus the original same-weight baseline was concentrated in drawdown control and 2025 behavior while preserving 2023/2024 participation.

This manifest should be treated as the benchmark before subsequent robustness tests, hedge ablations, sleeve ablations, or allocator work.
