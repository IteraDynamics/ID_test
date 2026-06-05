# Core v1 Risk Sleeve Ablation

Research-only robustness note.

## Tested configs

| Config | Trend | Equity | Gold | Risk sleeve | MR |
|---|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 0.40 | 0.35 | 0.15 | 0.10 | 0.00 |
| hedge05_45_35_15_05 | 0.45 | 0.35 | 0.15 | 0.05 | 0.00 |
| hedge00_50_35_15_00 | 0.50 | 0.35 | 0.15 | 0.00 | 0.00 |

## Results

| Config | CAGR | MaxDD | Sharpe | Calmar | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_40_35_15_10 | 14.17 | -17.80 | 1.017 | 0.796 | 24.90 | -8.70 | 28.94 | 24.28 | 4.80 |
| hedge05_45_35_15_05 | 14.60 | -19.04 | 0.990 | 0.767 | 26.53 | -9.22 | 30.45 | 25.09 | 4.00 |
| hedge00_50_35_15_00 | 15.00 | -20.18 | 0.966 | 0.743 | 28.09 | -9.72 | 31.87 | 25.85 | 3.27 |

Audit check stayed clean: 109,523 trend audit rows, all explicit_btc, zero fallback rows.

## Result

The baseline 10% risk sleeve remains the Core v1 setting.

Lower risk-sleeve weight increased CAGR but worsened MaxDD, Sharpe, Calmar, 2022, and 2025.

Core v1 remains:

```text
trend_weight   0.40
equity_weight  0.35
gold_weight    0.15
hedge_weight   0.10
mr_weight      0.00
```

Next robustness tests should keep the 10% risk sleeve fixed and test nearby shifts among trend, equity, and gold.
