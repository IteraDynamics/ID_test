# Core v1 Allocation Robustness

Research-only robustness note.

Branch: `gpt/core-v1-robustness-grid`  
Window: `2021-01-01` to `2025-12-31`  
Baseline: explicit BTC macro-state Core v1 Candidate

## Purpose

This note records the first allocation-neighborhood tests after Core v1 promotion.

The tests preserve the canonical explicit BTC state path and use the promoted canonical walk-forward runner.

## Baseline

```text
trend_weight   0.40
equity_weight  0.35
gold_weight    0.15
hedge_weight   0.10
mr_weight      0.00
```

Baseline result:

```text
CAGR      14.17
MaxDD    -17.80
Sharpe     1.017
Calmar     0.796
2021      24.90
2022      -8.70
2023      28.94
2024      24.28
2025       4.80
```

## Hedge / risk-sleeve ablation

| Config | Trend | Equity | Gold | Hedge | CAGR | MaxDD | Sharpe | Calmar | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 0.40 | 0.35 | 0.15 | 0.10 | 14.17 | -17.80 | 1.017 | 0.796 | 24.90 | -8.70 | 28.94 | 24.28 | 4.80 |
| hedge05_45_35_15_05 | 0.45 | 0.35 | 0.15 | 0.05 | 14.60 | -19.04 | 0.990 | 0.767 | 26.53 | -9.22 | 30.45 | 25.09 | 4.00 |
| hedge00_50_35_15_00 | 0.50 | 0.35 | 0.15 | 0.00 | 15.00 | -20.18 | 0.966 | 0.743 | 28.09 | -9.72 | 31.87 | 25.85 | 3.27 |

Observed pattern:

```text
less hedge -> higher CAGR
less hedge -> worse MaxDD
less hedge -> worse Sharpe
less hedge -> worse Calmar
less hedge -> worse 2022
less hedge -> worse 2025
```

Result: the 10% hedge remains in Core v1.

## Trend / equity / gold neighborhood

| Config | Trend | Equity | Gold | Hedge | CAGR | MaxDD | Sharpe | Calmar | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 0.40 | 0.35 | 0.15 | 0.10 | 14.17 | -17.80 | 1.017 | 0.796 | 24.90 | -8.70 | 28.94 | 24.28 | 4.80 |
| gold20_35_35_20_10 | 0.35 | 0.35 | 0.20 | 0.10 | 14.04 | -17.04 | 1.070 | 0.824 | 22.56 | -8.73 | 27.67 | 24.15 | 7.51 |
| eq30_gold20_40_30_20_10 | 0.40 | 0.30 | 0.20 | 0.10 | 14.03 | -17.92 | 1.009 | 0.783 | 23.13 | -8.55 | 28.25 | 24.41 | 5.90 |
| trend45_eq30_45_30_15_10 | 0.45 | 0.30 | 0.15 | 0.10 | 14.16 | -18.64 | 0.963 | 0.760 | 25.45 | -8.52 | 29.49 | 24.53 | 3.30 |

## Interpretation

The allocation neighborhood is robust. Nearby reasonable allocations remain close to baseline, but the shape differs.

Key observations:

```text
1. The 10% hedge remains useful.
2. Raising trend above 40% is not attractive on risk-adjusted metrics.
3. Moving gold from 15% to 20% is interesting only when funded from trend, not equity.
4. The strongest challenger is 35 trend / 35 equity / 20 gold / 10 hedge.
```

## Current ranking

```text
1. gold20_35_35_20_10
   Best risk-adjusted shape in this batch.
   Slightly lower CAGR than baseline, but better MaxDD, Sharpe, Calmar, and 2025.

2. baseline_40_35_15_10
   Official Core v1 baseline.
   Slightly higher CAGR than gold20 and already promoted/validated.

3. eq30_gold20_40_30_20_10
   Not compelling versus baseline or gold20.

4. trend45_eq30_45_30_15_10
   Similar CAGR to baseline but worse MaxDD, Sharpe, Calmar, and 2025.

5. hedge05_45_35_15_05
   Higher CAGR but worse shape than baseline.

6. hedge00_50_35_15_00
   Highest CAGR but weakest risk-adjusted profile in this batch.
```

## Resulting policy band

Treat Core v1 as a validated allocation neighborhood, not a single sacred point:

```text
trend_weight   0.35 to 0.40
equity_weight  0.35
gold_weight    0.15 to 0.20
hedge_weight   0.10
mr_weight      0.00
```

Operational labels:

```text
Core v1 baseline:      40 trend / 35 equity / 15 gold / 10 hedge
Core v1 smoother alt:  35 trend / 35 equity / 20 gold / 10 hedge
```

## Decision

Do not replace Core v1 baseline yet.

Document `gold20_35_35_20_10` as the strongest robustness challenger and possible Core v1.1 smoother/defensive allocation.

The next tests should investigate whether the gold20 improvement is persistent across additional history, alternate OOS boundaries, or sleeve/timeframe ablations.
