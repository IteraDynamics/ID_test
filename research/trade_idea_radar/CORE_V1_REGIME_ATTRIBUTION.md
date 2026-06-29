# Core v1 Regime Attribution

## Purpose

This memo defines the next Core v1 validation gate after cost sensitivity.

Cost sensitivity is complete and merged. The relevant question is no longer whether the leading allocation survives higher costs. The relevant question is whether its edge is broad, stable, and explainable across market regimes, or whether the full-period improvement is being carried by one narrow/favorable regime.

Core v1 objective:

> Best attainable portfolio performance while remaining institutionally protective and responsible with capital.

## Allocation under review

Leading candidate:

`candidate_btc1h_hedges_to_btc4h_gld_qqq`

Plain-English thesis:

> Remove noisy / expensive BTC 1H trend exposure and low-value hedge sleeves. Reallocate that capital into cleaner BTC 4H trend, QQQ compounding, and GLD ballast.

Conservative fallback:

`candidate_btc1h_half_btc4h_half_qqq`

The fallback keeps hedge sleeves and moves only BTC 1H capital into BTC 4H and QQQ. It exists to confirm whether the same broad thesis holds with smoother risk and less 2022 weakness.

## Canonical data provenance

This gate must use the canonical 2018-2025 crypto files and daily cross-asset files:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/SPY_1D.csv`
- `data/QQQ_1D.csv`
- `data/BIL_1D.csv`
- `data/GLD_1D.csv`

The older 2019-start BTC/ETH files remain rejected for accepted Core v1 validation because they caused parity drift.

The regime-attribution runner enforces these canonical paths by default and raises on data-path drift.

## Implementation

Primary runner:

```text
scripts/run_core_v1_regime_attribution.py
```

Output directory:

```text
artifacts/core_v1_regime_attribution/
```

The regime runner is additive. It does not modify Core v1 strategy logic. It calls the canonical candidate WFO runner for the three required scenarios and then performs deterministic attribution on the stitched daily OOS NAVs.

Required scenarios:

1. `baseline_40_35_15_10`
2. `candidate_btc1h_hedges_to_btc4h_gld_qqq`
3. `candidate_btc1h_half_btc4h_half_qqq`

## Command

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1

python scripts\run_core_v1_regime_attribution.py `
  --workers 3
```

To reuse already-generated stitched NAVs in the attribution directory:

```powershell
python scripts\run_core_v1_regime_attribution.py `
  --workers 3 `
  --skip-run
```

## Regime buckets

The initial regime labels are deliberately deterministic and simple. This is not a classifier or model-selection layer.

### 1. Calendar year

Buckets:

- 2020
- 2021
- 2022
- 2023
- 2024
- 2025

Purpose:

Answer whether the leading candidate is carried by one year.

### 2. Known stress windows

Buckets:

- `covid_2020_drawdown`: 2020-02-19 to 2020-03-23
- `covid_2020_drawdown_recovery`: 2020-02-19 to 2020-06-30
- `bear_tightening_2021_2022`: 2021-11-09 to 2022-12-19
- `bear_tightening_recovery`: 2021-11-09 to 2023-11-22
- `calendar_2022`: 2022-01-01 to 2022-12-31
- `calendar_2025`: 2025-01-01 to 2025-12-31

Purpose:

Check whether the 2022 weakness and 2025 recovery improvement are isolated, explainable, and acceptable.

### 3. Portfolio drawdown state

Scenario-specific daily drawdown labels:

- `new_high`
- `shallow_drawdown`
- `deep_drawdown`
- `recovery`

The drawdown-state label is one-day lagged so the current return is not labeled using its own close.

Purpose:

Check whether the candidate improves behavior during recovery and whether drawdown-state performance supports freezing the allocation.

### 4. Equity regime

Daily labels based on SPY and QQQ relative to their 175-day moving averages:

- `equity_uptrend`
- `equity_downtrend`
- `equity_mixed`

Signals are one-day lagged.

Purpose:

Check whether increased QQQ exposure is simply harvesting equity uptrends or remains acceptable outside equity-friendly conditions.

### 5. Crypto regime

Daily labels based on BTC 50-day / 200-day trend and BTC close versus the 200-day moving average:

- `crypto_uptrend`
- `crypto_downtrend`
- `crypto_mixed`

Signals are one-day lagged.

Purpose:

Check whether the candidate is over-dependent on crypto bull regimes after removing BTC 1H and hedge sleeves.

### 6. Volatility regime

Daily labels based on BTC 21-day realized volatility versus rolling 252-day 33rd/67th percentiles:

- `vol_low`
- `vol_mid`
- `vol_high`

Realized-volatility and percentile thresholds are one-day lagged.

Purpose:

Check whether the allocation remains acceptable in high-volatility conditions.

## Metrics per bucket

Each summary table includes:

- number of observations
- total return
- annualized return where enough observations exist
- annualized volatility
- Sharpe where enough observations exist
- max drawdown
- worst 21-day return
- worst 63-day return
- positive-day rate
- final equity from a normalized 100,000 starting equity
- delta versus same-bucket baseline

For non-contiguous regime buckets, rolling 21-day and 63-day metrics are computed over selected observations rather than uninterrupted calendar windows. Stress-window and calendar-year summaries remain contiguous.

## Outputs

The runner writes:

```text
artifacts/core_v1_regime_attribution/year_summary.csv
artifacts/core_v1_regime_attribution/stress_window_summary.csv
artifacts/core_v1_regime_attribution/drawdown_state_summary.csv
artifacts/core_v1_regime_attribution/drawdown_events.csv
artifacts/core_v1_regime_attribution/equity_regime_summary.csv
artifacts/core_v1_regime_attribution/crypto_regime_summary.csv
artifacts/core_v1_regime_attribution/vol_regime_summary.csv
artifacts/core_v1_regime_attribution/scenario_daily_returns.csv
artifacts/core_v1_regime_attribution/regime_labels.csv
artifacts/core_v1_regime_attribution/metadata.json
artifacts/core_v1_regime_attribution/CORE_V1_REGIME_ATTRIBUTION_RESULTS.md
```

## Questions this gate must answer

1. Is the edge concentrated in one year?
2. Is the edge concentrated in risk-on / crypto bull conditions?
3. Does the candidate remain acceptable during risk-off / crypto bear / high-vol regimes?
4. Is the 2022 weakness isolated, explainable, and acceptable?
5. Does the conservative fallback confirm the same thesis with smoother risk?
6. Does the candidate improve recovery behavior enough to justify the 2022 blemish?
7. Is the candidate robust enough to freeze allocation before live signal readiness?

## Decision rule

### GREEN

Proceed toward allocation freeze / live signal readiness if:

- The leading candidate reproduces accepted default full-period results.
- It beats baseline across full-period CAGR, total return, Sharpe, Calmar, final equity, and max drawdown.
- Annual attribution does not show the edge being explained by only one year.
- Stress-window attribution shows the 2022 weakness is bounded and explainable.
- Risk-off / crypto-down / high-vol buckets remain acceptable.
- Recovery behavior is meaningfully improved versus baseline.
- The conservative fallback confirms the same thesis with smoother drawdown behavior.

### YELLOW

Do not freeze the aggressive allocation yet if:

- The candidate wins full-period, but attribution shows material dependence on one favorable regime.
- The fallback confirms the thesis more responsibly than the aggressive candidate.
- 2022 weakness is acceptable but not yet clearly offset by recovery improvement.

YELLOW likely means keep the candidate as the leading allocation but prefer fallback or a policy selector for live readiness.

### RED

Reject or revise the aggressive allocation if:

- The edge is carried by one narrow year or regime.
- Risk-off / crypto-down / high-vol attribution is materially worse than baseline.
- 2022 weakness is not isolated or not offset by faster recovery / stronger later drawdown behavior.
- The fallback fails to confirm the redistribution thesis.

## Current status

Implementation is present, but accepted regime-attribution results require running the script locally against the canonical data files. Do not mark this gate GREEN until the generated artifacts are reviewed.

_Research only. Not financial advice._
