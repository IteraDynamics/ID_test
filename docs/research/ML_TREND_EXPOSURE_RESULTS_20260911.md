# Trend exposure mapping — results, 2026-09-11

Decision: continue research on the cash-capped 2x implementation and the 2.5x/3x region only if the user accepts the risk budget. Do not promote 4x on this evidence. No exposure setting is authorized for live use.

The fixed ladder answers the question: additional exposure materially improves net compounded return initially, but financing and volatility increasingly consume the benefit. This is scaling an existing signal, not finding new predictive information.

Observed adjusted-price simulation, February 1, 2018–December 31, 2024. Primary assumes 10bps one-way trading costs and a hypothetical fixed 8% annual rate on actual outstanding borrowing, ACT/365. BIL earns observed adjusted returns. Multipliers apply to original risky target weights; they are not constant leverage ratios.

| Scaling | Net CAGR | Max drawdown | Annual volatility | Average risky exposure | Longest underwater, calendar days |
|---|---:|---:|---:|---:|---:|
| 1x | 5.49% | 5.93% | 5.37% | 39.81% | 651 |
| 1.5x | 7.08% | 9.30% | 8.04% | 59.66% | 769 |
| 2x_cashcap | 8.67% | 12.90% | 10.52% | 77.72% | 937 |
| 2x | 8.53% | 12.90% | 10.71% | 79.49% | 937 |
| 2.5x | 9.38% | 16.93% | 13.38% | 99.31% | 1029 |
| 3x | 9.91% | 21.08% | 16.04% | 119.13% | 1029 |
| 4x | 10.36% | 29.29% | 21.37% | 158.78% | 1029 |

The 2x cash cap raises CAGR by 3.18 percentage points versus 1x, with historical drawdown increasing from 5.94% to 12.90%. It avoids borrowing and outperforms uncapped 2x under the primary financing assumption. From 3x to 4x, CAGR gains only 0.45 percentage points while drawdown grows by 8.21 points. A 30% acceptable live drawdown would therefore not justify selecting the 29.29% historical-drawdown row.

## Financing and implementation sensitivity

| Scaling | 4% funding CAGR | 8% funding CAGR | 12% funding CAGR | 25bps costs CAGR (8% funding) | One-session delay CAGR (8% funding) |
|---|---:|---:|---:|---:|---:|
| 1x | 5.49% | 5.49% | 5.49% | 5.10% | 5.34% |
| 1.5x | 7.08% | 7.08% | 7.08% | 6.52% | 6.85% |
| 2x_cashcap | 8.67% | 8.67% | 8.67% | 7.97% | 8.36% |
| 2x | 8.61% | 8.53% | 8.45% | 7.83% | 8.20% |
| 2.5x | 9.88% | 9.38% | 8.88% | 8.59% | 8.93% |
| 3x | 11.05% | 9.91% | 8.78% | 9.04% | 9.35% |
| 4x | 13.12% | 10.36% | 7.65% | 9.27% | 9.53% |

Funding sensitivities are alternative hypothetical flat rates, not historical broker financing reconstructions. Costs and delay stresses are individual scenarios, not a combined worst case. Cumulative financing at 4x is $0.4825 per initial $1 across the full simulation; this is not an annual percentage cost. Broker eligibility, collateral treatment and realized execution remain unverified.

## Tail and recovery diagnostics

Doubling risky overnight and intraday percentage moves while freezing original historical targets produces drawdowns of 28.63% at 2x cash-capped, 35.49% at 2.5x, 41.81% at 3x and 53.13% at 4x. This synthetic replay amplifies favorable as well as adverse moves: it is a fragility diagnostic, not a forecast, probability estimate, or purely adverse scenario. It does not regenerate trend signals from synthetic history.

An instantaneous correlated 20% risky-asset gap at maximum observed risky exposure implies approximately 20.0% equity loss for cash-capped 2x, 31.8% for 2.5x, 38.7% for 3x and 53.2% for 4x, before incremental liquidation costs. These are losses from that instant, not full peak-to-trough drawdowns or loss bounds.

No simulated path triggered the stylized 30% equity/gross daily-open maintenance stop. That says nothing about intraday collateral calls, asset-specific requirements or broker eligibility. At 4x the highest observed gross exposure was 2.6583 times equity.

At the end of 2024, cash-capped 2x remained below its high-water mark for 937 calendar days; 2.5x, 3x and 4x remained underwater for 1,029 days. Positive annual returns can coexist with a still-unrecovered earlier peak. Both depth and duration belong in the risk mandate.

Excluding 2020, annualized arithmetic mean return rises from 5.12% at 1x to 7.68% at cash-capped 2x and 10.30% at 4x; volatility rises from 5.44% to 10.70% and 21.59%, respectively. These disjoint-period statistics are not continuous-path CAGRs or drawdowns.

## Evidence and reproducibility

42 reconciled paths; four mechanics tests; seven primary paths replayed with an independent holdings/debit implementation and a different fee-equation solver. Original 1x NAV reproduced to floating-point tolerance. Source identities match the retained foundation. Full CSV hashes, code hashes and environment are in report.json. All 2018–24 results are exploratory on previously inspected history; no fresh OOS claim and no 2025 use.

Commands (repository root; replace paths with local equivalents):

```powershell
uv run --locked --python 3.12 python -m research.ml_development.trend_exposure --etf-root <ETF_DIRECTORY> --energy-zip <ENERGY_ZIP> --crop-zip <CROP_ZIP> --output-dir <NEW_OUTPUT_DIRECTORY>
uv run --locked --python 3.12 python -m scripts.research_probes.verify_trend_exposure_20260911 --etf-root <ETF_DIRECTORY> --energy-zip <ENERGY_ZIP> --crop-zip <CROP_ZIP> --output-dir <OUTPUT_DIRECTORY>
```

The next decision is the maximum tolerable strategy-equity drawdown in a difficult future path, together with tolerance for multi-year recovery. It cannot be inferred from the best historical return. Additional exposure beyond 3x looks unattractive under the primary financing assumption; cheaper implementable financing could change that assessment.
