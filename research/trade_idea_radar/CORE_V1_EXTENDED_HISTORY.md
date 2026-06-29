# Core v1 Extended History Validation

Research-only robustness note.

Branch: `gpt/core-v1-extended-history`  
Window: `2020-01-01` to `2025-12-31`  
Baseline: explicit BTC macro-state Core v1 Candidate

## Purpose

This note records the extended-history validation performed after Core v1 allocation and boundary robustness testing.

The purpose was not to replace the blessed Core v1 baseline. The purpose was to test whether the baseline and strongest smoother challenger remain robust when an additional OOS regime, 2020, becomes scoreable.

The test follows the falsification-oriented interpretation of the research process:

```text
more history -> more chances to break the thesis
not -> proof that the thesis is true
```

## Data extension

A Coinbase Exchange hourly OHLCV fetcher was added:

```text
scripts/fetch_coinbase_hourly_history.py
```

Generated files:

```text
data/btcusd_3600s_2018-01-01_to_2025-12-31.csv
data/ethusd_3600s_2018-01-01_to_2025-12-31.csv
```

Fetch summary:

```text
BTC-USD rows: 70069  2018-01-01 00:00:00 -> 2025-12-31 00:00:00
ETH-USD rows: 70086  2018-01-01 00:00:00 -> 2025-12-31 00:00:00
BTC gaps > 1h: 14
ETH gaps > 1h: 10
```

A flexible OHLCV overlap comparison utility was added:

```text
scripts/compare_ohlcv_overlap.py
```

Overlap checks versus the pre-existing research files showed:

```text
ETH overlap: exact close match on common rows
BTC overlap: source/venue differences versus old research BTC file
```

BTC overlap detail:

```text
common rows:              61331
max close pct diff:       2.587668%
mean close pct diff:      0.071657%
rows > 0.10% close diff:  7719
```

ETH overlap detail:

```text
common rows:              59748
max close pct diff:       0.000000%
mean close pct diff:      0.000000%
rows > 0.10% close diff:  0
```

Interpretation:

```text
ETH was successfully extended backward.
BTC became a Coinbase-source alternate/replacement dataset.
```

Therefore, before running the 2020-2025 extended-history test, a canonical-window source sanity check was required.

## Coinbase-source sanity check: 2021-2025

The first test reused the canonical OOS window while using the newly fetched crypto files.

Purpose:

```text
verify that changing BTC source does not materially alter the already-blessed 2021-2025 behavior
```

### Baseline: 40 / 35 / 15 / 10

```text
trend_weight   0.40
equity_weight  0.35
gold_weight    0.15
hedge_weight   0.10
mr_weight      0.00
```

Result:

```text
CAGR      14.20
MaxDD    -17.88
Sharpe     1.014
Calmar     0.794
2021      25.17
2022      -8.65
2023      28.56
2024      24.26
2025       5.02
Audit rows written: 109486
```

### Gold20 challenger: 35 / 35 / 20 / 10

```text
trend_weight   0.35
equity_weight  0.35
gold_weight    0.20
hedge_weight   0.10
mr_weight      0.00
```

Result:

```text
CAGR      14.07
MaxDD    -17.11
Sharpe     1.067
Calmar     0.823
2021      22.81
2022      -8.70
2023      27.34
2024      24.14
2025       7.72
Audit rows written: 109486
```

### Source sanity conclusion

The Coinbase-source canonical-window results were very close to the existing research results.

The same baseline-vs-gold20 relationship persisted:

```text
baseline -> slightly higher CAGR and upside capture
gold20   -> shallower drawdown, higher Sharpe, higher Calmar, stronger 2025
```

This allowed the extended-history test to proceed.

## Extended-history test: 2020-2025

The extended test used OOS start `2020-01-01`, adding the COVID crash/recovery regime as a newly scoreable OOS fold.

This is not ML training. Earlier history is used as warmup/context for long-horizon state and indicators. The key value is that 2020 becomes an additional out-of-sample regime.

## Extended baseline: 40 / 35 / 15 / 10

Artifacts:

```text
artifacts/extended_history_2020_2025/baseline_40_35_15_10
```

Result:

```text
CAGR      18.51
MaxDD    -17.88
Sharpe     1.223
Calmar     1.035
2020      42.57
2021      25.17
2022      -8.65
2023      28.56
2024      24.26
2025       5.02
Audit rows written: 131440
```

## Extended gold20 challenger: 35 / 35 / 20 / 10

Artifacts:

```text
artifacts/extended_history_2020_2025/gold20_35_35_20_10
```

Result:

```text
CAGR      17.92
MaxDD    -17.11
Sharpe     1.264
Calmar     1.048
2020      39.17
2021      22.81
2022      -8.70
2023      27.34
2024      24.14
2025       7.72
Audit rows written: 131440
```

## Extended comparison

| Config | Trend | Equity | Gold | Hedge | CAGR | MaxDD | Sharpe | Calmar | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 0.40 | 0.35 | 0.15 | 0.10 | 18.51 | -17.88 | 1.223 | 1.035 | 42.57 | 25.17 | -8.65 | 28.56 | 24.26 | 5.02 |
| gold20_35_35_20_10 | 0.35 | 0.35 | 0.20 | 0.10 | 17.92 | -17.11 | 1.264 | 1.048 | 39.17 | 22.81 | -8.70 | 27.34 | 24.14 | 7.72 |

Gold20 versus baseline:

```text
CAGR:    -0.59 pts
MaxDD:   +0.77 pts shallower
Sharpe:  +0.041
Calmar:  +0.013
2020:    -3.40 pts
2021:    -2.36 pts
2022:    -0.05 pts
2023:    -1.22 pts
2024:    -0.12 pts
2025:    +2.70 pts
```

## Interpretation

The extended-history result strengthens the same pattern observed in allocation, boundary, and source-sanity testing.

Observed pattern:

```text
baseline -> higher-upside expression
gold20   -> smoother risk-adjusted expression
```

The 2020 fold did not expose fragility. Adding 2020 materially improved the stitched baseline profile without increasing MaxDD.

For gold20, the smoother-allocation thesis survived the newly added 2020 regime:

```text
gold20 gives up moderate upside in 2020/2021/2023
gold20 improves MaxDD, Sharpe, Calmar, and 2025
gold20 does not materially worsen 2022
```

## Decision

Do not replace the blessed Core v1 baseline yet.

Document the validated allocation band as:

```text
trend_weight   0.35 to 0.40
equity_weight  0.35
gold_weight    0.15 to 0.20
hedge_weight   0.10
mr_weight      0.00
```

Operational labels:

```text
Core v1 official baseline: 40 trend / 35 equity / 15 gold / 10 hedge
Core v1 smoother candidate: 35 trend / 35 equity / 20 gold / 10 hedge
```

Current conclusion:

```text
Baseline remains the official Core v1 expression.
Gold20 remains the strongest Core v1.1 smoother/defensive candidate.
```

## Next tests

Recommended next steps:

```text
1. Verify explicit BTC audit state for the 2020-2025 artifacts.
2. Add a source/warmup note explaining why 2020 is newly scoreable.
3. Consider a small year-boundary stress set, e.g. 2020-2024 and 2021-2025 side by side.
4. Do not add confidence sizing until the current fixed-weight Core v1 evidence is documented and merged.
```
