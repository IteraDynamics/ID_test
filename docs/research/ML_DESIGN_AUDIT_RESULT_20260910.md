# Learning-design audit results — 2026-09-10

Completed70 real optimizer fits plus8 synthetic fits under the recorded budget.
All prior results unchanged. Cash-permitted objective is now approved. No2025 or
Core/runtime changes, no production or statistical-significance claim.

## Known-signal checks

Production fitting/stopping pipeline recovers planted linear signal: MSE reduction
versus zero is99.23% Ridge,97.46% GBM,99.13% MLP. Training-label permutation removes
recovery: -0.014%,+1.38%,-0.98%, respectively. All predeclared checks pass.
This rules out gross failure to learn a strong simple relationship, not subtle
bugs, weak feature extraction, model misspecification or absent market signal.

## Same-date rank correlation

| Model/objective | All years | Excluding2020 |
|---|---:|---:|
| Historical mean control |.09759|.09685|
| Ridge raw return |.07516|.06653|
| Ridge rank target |.08595|.08689|
| GBM raw return |.02976|.02600|
| GBM rank target |.07751|.07521|
| MLP raw return |.03101|.01853|
| MLP rank target |.04487|.04571|

Target design matters: rank training improves ordering, especially forGBM, and
that pattern persists outside2020. None exceeds the historical-mean control.
These are average correlations across8-asset weekly cross-sections, not pooled
correlations or trade returns. One seed, overlapping labels, correlated ETFs.

Risk-scaledGBM improves raw-return MSE1.37% versus historical mean overall but
worsens0.46% excluding2020. Risk-scaledMLP worsens16.64% overall. Risk normalization
is not an automatic solution; target scale and optimizer interactions remain.

## Earlier neural checkpoints

Inspecting every epoch selects6,2,6,2,19,86,5 epochs in2018–2024. Raw MLP's overall
MSE advantage versus past mean falls from0.375% to0.196%; excluding2020 it worsens
from2.63% to2.99% above the control. Missing epochs1–4 was a legitimate concern,
but this controlled comparison does not identify it as the main bottleneck.

2020 contributes roughly33% of prior selected squared error from14.6% of rows.
Loss curves and asset/year/known-volatility error contributions are retained.
The central unresolved issue is whether time-varying price/volume information adds
stable value beyond slow per-ETF mean differences. The audit does not prove that
all available information is weak or that another architecture would work.

## Reporting correction and validation

An initial metric inventory matched the metadata column risk_scale as a forecast
because of its prefix. Corrected to an explicit12-series inventory and regenerated
metrics from the unchanged forecasts. Zero additional fits. Original executed
runner and its digest preserved; current postprocessor digest separately recorded.
A canary now ensures metadata cannot become a reported model. This was a reporting
inventory defect, not the cause of previous weak model results.

Next: common cash-permitted portfolio mapping in ML_PORTFOLIO_DIAGNOSTIC_PLAN_20260910.md.
Need adjusted BIL input and manifest before economically evaluating cash allocation.
No further model or hyperparameter search is authorized by this result.
