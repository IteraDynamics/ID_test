# Core v1 Boundary Robustness

Research-only robustness note.

Branch: `gpt/core-v1-boundary-robustness`  
Primary question: does the strongest smoother challenger remain competitive when the OOS boundary is shifted from `2021-01-01` to `2022-01-01`?

## Context

The blessed Core v1 Candidate remains:

```text
trend_weight   0.40
equity_weight  0.35
gold_weight    0.15
hedge_weight   0.10
mr_weight      0.00
```

Canonical blessed validation window:

```text
2021-01-01 to 2025-12-31
```

Canonical blessed result:

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

The strongest allocation-neighborhood challenger from the prior robustness batch was:

```text
trend_weight   0.35
equity_weight  0.35
gold_weight    0.20
hedge_weight   0.10
mr_weight      0.00
```

This note compares the blessed structure against that challenger over a secondary boundary window:

```text
2022-01-01 to 2025-12-31
```

## Boundary-window comparison

| Config | Trend | Equity | Gold | Hedge | CAGR | Total Return | MaxDD | Sharpe | Calmar | Volatility | Final Equity | 2022 | 2023 | 2024 | 2025 | Audit Rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 0.40 | 0.35 | 0.15 | 0.10 | 11.65 | 55.36 | -14.25 | 0.897 | 0.817 | 13.26 | 155355.80 | -8.70 | 28.94 | 24.28 | 4.80 | 87623 |
| gold20_35_35_20_10 | 0.35 | 0.35 | 0.20 | 0.10 | 12.01 | 57.38 | -12.87 | 0.973 | 0.933 | 12.46 | 157380.32 | -8.73 | 27.67 | 24.15 | 7.51 | 87623 |

## Direct difference: gold20 minus baseline

```text
CAGR          +0.36 percentage points
Total Return  +2.02 percentage points
MaxDD         +1.38 percentage points shallower
Sharpe        +0.076
Calmar        +0.116
Volatility    -0.80 percentage points
Final Equity  +2024.52
2022          -0.03 percentage points
2023          -1.27 percentage points
2024          -0.13 percentage points
2025          +2.71 percentage points
```

## Audit

Both runs wrote `87,623` audited trend rows.

Required source counts for both runs:

```text
btc_state_source              {'explicit_btc': 87623}
btc_parabolic_state_source    {'explicit_btc': 87623}
```

No asset-local fallback was observed in either run.

## Interpretation

The shifted boundary does not replace the blessed Core v1 canonical score. It is a secondary robustness view.

The comparison asks whether `gold20_35_35_20_10` still looks like the smoother challenger when 2021 is excluded from the scored OOS window.

Result: yes.

Over the `2022-01-01` to `2025-12-31` boundary window, gold20 improved the stitched portfolio on CAGR, total return, MaxDD, Sharpe, Calmar, volatility, final equity, and 2025 return. It was slightly worse in 2022, worse in 2023, and roughly flat/slightly worse in 2024.

The improvement is therefore not annual dominance across every year. It is a stitched-path and portfolio-shape improvement, driven materially by shallower drawdown, lower volatility, and a better 2025.

## Decision

Do not rewrite the blessed Core v1 Candidate manifest.

Maintain official Core v1 baseline as:

```text
40 trend / 35 equity / 15 gold / 10 hedge / 0 MR
```

Promote the evidence status of `gold20_35_35_20_10` from:

```text
strongest allocation-neighborhood challenger
```

to:

```text
leading Core v1.1 smoother-allocation candidate
```

pending extended-history validation, preferably including earlier crypto regimes such as 2018 if clean data can be sourced.

## Next recommended validation

1. Add earlier clean crypto history, especially 2018 if available.
2. Re-run the blessed baseline and gold20 challenger across an extended OOS set.
3. Promote gold20 only if it remains superior or clearly more robust across additional regime exposure.
