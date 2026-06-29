# Explicit BTC Core Baseline

## Summary

The current Core candidate uses BTC as the crypto regime anchor and treats ETH as a participation asset. ETH trend sleeves still trade ETH-local price action, but recovery/parabolic risk state is sourced from BTC-only macro columns injected by the runner.

This document records the promoted baseline after the explicit cross-asset state audit.

## Why this matters

The previous implementation allowed an ETH sleeve to compute BTC-labeled recovery/parabolic state from ETH-local data. That created documentation/code drift and made it unclear whether tests were evaluating the intended architecture.

The promoted path fixes this by making state ownership explicit:

```text
BTC data -> canonical BTC macro state -> injected columns -> strategy metadata/audit
```

## Canonical columns

- `btc_above_sma175`
- `btc_extension_sma365`
- `btc_parabolic_soft`
- `btc_parabolic_hard`
- `btc_parabolic_tier`

## Promoted result

OOS window: 2021-01-01 to 2025-12-31

Weights:

```text
trend   0.40
equity  0.35
gold    0.15
hedge   0.10
mr      0.00
```

Promoted explicit-BTC result:

```text
CAGR          14.17%
Total Return  93.91%
MaxDD        -17.80%
Sharpe         1.017
Calmar         0.796
Ann Vol       14.01%
2021         +24.90%
2022          -8.70%
2023         +28.94%
2024         +24.28%
2025          +4.80%
```

Original same-weight result:

```text
CAGR          12.66%
Total Return  81.45%
MaxDD        -18.68%
Sharpe         0.947
Calmar         0.678
Ann Vol       13.59%
2021         +29.00%
2022         -11.34%
2023         +27.87%
2024         +25.08%
2025          -2.02%
```

## Interpretation

The promoted result is better, but the reason for promotion is not raw performance chasing. The reason is architectural correctness:

- less ambiguous cross-asset state ownership
- audit rows prove trend sleeves consume explicit BTC state
- ETH no longer silently uses ETH-local state for BTC-labeled logic
- 2022/2025 behavior improves while 2023/2024 participation is preserved

## Required audit evidence

Canonical runs must write `cross_asset_state_audit.csv` and should show:

```text
btc_state_source = explicit_btc
btc_parabolic_state_source = explicit_btc
```

Any `asset_local_fallback` row means the run is not canonical and must be inspected.

## Not productionized

This remains a research baseline. It is not production fund infrastructure and does not change execution, live trading, compliance, monitoring, or capital allocation policy.
