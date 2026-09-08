# Post-012 evidence review — 2026-09-08

**Completed:** review of existing result records and ranking implementation.
**Recommendation:** a no-refit price-Ridge baseline diagnostic before any portfolio test.
**Not executed:** new data analysis, model fitting, portfolio simulation or holdout use.

## What the existing evidence establishes

| Evidence | Finding | Remaining question |
| --- | --- | --- |
| [005](ML_LAB_EXPERIMENT_005_RESULTS.md) | Expanding Ridge mean IC 0.06382 versus 0.00241 for 60d momentum over 650 OOS anchors | Increment beyond other simple rankings was not established |
| [006](ML_LAB_EXPERIMENT_006_RESULTS.md) | Volatility relationships weakened after 2021; GBM deterioration had asset concentration | The audit explained GBM deterioration, not Ridge's independent economic value |
| [007](ML_LAB_EXPERIMENT_007_RESULTS.md) | Trailing-3y Ridge post-2021 IC 0.0531 versus expanding 0.0300 | Memory comparison was exploratory, not an independently selected winner |
| [008](ML_LAB_EXPERIMENT_008_RESULTS.md) | Nonlinear tail increment was inconsistent and concentrated | This closes nonlinear increment, not a positive validation of Ridge |
| [009](ML_LAB_EXPERIMENT_009_RESULTS.md) | Trailing-3y price Ridge full IC/spread 0.05767/0.06535; post-2021 0.05309/0.05649 | How much is simple volatility/momentum ordering? |
| [010](ML_LAB_EXPERIMENT_010_RESULTS.md), [011](ML_LAB_EXPERIMENT_011_RESULTS.md), [012](ML_LAB_EXPERIMENT_012_RESULTS.md) | Macro recurrence was concentrated, transfer failed, compact simplification failed | These findings do not establish net returns for the surviving baseline |

005–008 and 009–012 do not have identical evaluation support. In particular, 005
began OOS evaluation in 2012 (650 anchors); 009/012 evaluate 2007–2024 (902 anchors).
Do not attribute differences in pooled metrics solely to model changes. Any new
paired comparison must use one exact saved row/anchor inventory.

## Portfolio evidence gap

The reviewed ML Lab specifications, results and implementations measure ranking
and target separation. Experiment 005 explicitly excludes weights and simulated
trading. No net-return, turnover or transaction-cost result for these exact saved
price-Ridge predictions was found in this ML Lab scope. Other Itera portfolio
work does not substitute for evaluation of this particular signal and mapping.

In `research/ml_lab/cross_sectional_v1.py`, `_build_panel` defines the raw target as
20-session close return divided by trailing 60-session log-return volatility times
sqrt(20). Thus a positive target spread is not a return spread. Dependence on a
volatility-normalized target is a reason to inspect simple low-volatility rankings;
it does not by itself prove an artifact, leakage or a useless signal.

## Recommended next diagnostic (proposal, not frozen Experiment 013)

Question: does saved price-only Ridge provide chronological information beyond
simple low-volatility and momentum rankings on exactly the same observations?

- Use the existing frozen 14-ETF files and Experiment 009 saved predictions.
  Reuse Experiment 012 input hashes, cutoff and parity checks; no data refresh.
- Keep trailing-3y primary and expanding as context. Use all 902 eligible anchors,
  pre-2022, 2022–2024 and every year; no favorable-period selection.
- Compare saved price Ridge with fixed negative 60d volatility rank, positive 60d
  momentum rank and positive 120d momentum rank. No sign/window/composite search.
- Report original-target IC/spreads, score agreement and paired differences.
  Separately inspect the unscaled 20-session close-return numerator, clearly
  labeled as a diagnostic outcome rather than a changed training target.
- Attribute results across every ETF and inspect selection persistence. Selection
  changes are not portfolio turnover without a defined weighting/execution rule.
- No refit, new model, portfolio optimization, naive independent-anchor p-values
  or reserved 2025 use. Do not label another discovery diagnostic confirmation.

Before implementation, fix tie handling, tail size, exact output inventory and
descriptive disposition in a separate specification. If Ridge adds little beyond
the fixed simple rankings, that weakens the case for a portfolio experiment. If
increments recur across both periods and years, the diagnostic can justify a
separate research portfolio design; it cannot establish net profitability.

This revises the earlier suggestion to move directly toward a portfolio experiment:
the existing evidence leaves a simpler baseline question unresolved first.
