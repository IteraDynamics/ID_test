# ML Lab Experiment 006 — Cross-Sectional Stability Audit Results

## Status

**EXPLORATORY / DIAGNOSTIC / NON-CONFIRMATORY**

This record belongs only to the isolated ML Lab. It does not authorize any Core, runtime, strategy, threshold, order, NAV, exposure, portfolio, paper-trading, live-trading, or capital change.

No model was refit or tuned in Experiment 006. The reserved Campaign #50 2025 holdout was not used.

## Question

Why did the nonlinear cross-sectional edge observed in Experiment 005 reverse after 2021?

The audit examined three descriptive mechanisms without changing the Experiment 005 model specification:

1. relationship shift,
2. model brittleness,
3. asset concentration.

## Main result

All three mechanisms were present descriptively.

### Pre-2022 model behavior

2012–2021:

- GBM mean rank IC: **0.10038**
- Ridge mean rank IC: **0.07371**
- GBM minus Ridge: **+0.02667**
- GBM positive-IC fraction: **0.6044**
- Ridge positive-IC fraction: **0.5845**

### Post-2021 model behavior

2022–2024:

- GBM mean rank IC: **-0.00190**
- Ridge mean rank IC: **0.02998**
- GBM minus Ridge: **-0.03188**
- GBM positive-IC fraction: **0.5034**
- Ridge positive-IC fraction: **0.5034**

The nonlinear advantage did not merely weaken; it reversed.

## Relationship shift

The strongest Experiment 005 state variables changed materially after 2021.

Mean yearly simple feature IC changes, post minus pre:

- `vol_60d_xrank`: **+0.09395**; pre **-0.11045**, post **-0.01651**
- `vol_20d_xrank`: **+0.08222**; pre **-0.08821**, post **-0.00599**
- `vol_ratio_20_60_xrank`: **-0.04993**; pre **+0.04108**, post **-0.00884**
- `drawdown_120_xrank`: **-0.01824**
- `ret_120d_xrank`: **+0.01080**

`vol_ratio_20_60_xrank` changed sign. The historically strong negative volatility-rank relationships moved substantially toward zero.

This is direct descriptive evidence that the cross-sectional geometry changed.

## Model brittleness

The GBM did not reduce its reliance on the relationships that were deteriorating.

Largest GBM importance changes included:

- `vol_60d_xrank`: **0.27491 -> 0.32446**
- `vol_ratio_20_60_xrank`: **0.09629 -> 0.12940**
- `vol_20d_xrank`: **0.05045 -> 0.06759**
- `range_position_120_xrank`: **0.05646 -> 0.00300**
- `drawdown_120_xrank`: **0.09850 -> 0.07477**

Thus the nonlinear model became more concentrated in volatility-state features while those features' simple relationships were weakening or changing sign.

Ridge importance shifts were smaller in absolute magnitude, consistent with a smoother, less brittle representation.

## Asset concentration

The deterioration was not uniform across the universe.

The top three positive deterioration contributors were:

1. `XLU` — 28.96% of positive deterioration attribution
2. `XLF` — 17.76%
3. `XLB` — 13.73%

Together they accounted for **60.46%** of positive deterioration attribution.

Additional meaningful contributors included `IWM`, `RSP`, `IWF`, and `MDY`.

This indicates that the post-2021 break had material cross-sectional concentration rather than appearing identically across all assets.

## Interpretation

Experiment 006 supports the following exploratory diagnosis:

> Experiment 005 found useful nonlinear cross-sectional structure, but that structure was regime-sensitive. After 2021 the underlying relationships changed, and the expanding GBM retained greater dependence on the older nonlinear volatility-state geometry than Ridge did.

This does **not** establish that a shorter-memory model is superior. It establishes a concrete reason to test model-memory adaptivity without changing model family, features, target, or hyperparameters.

## Next experiment justified

Experiment 007 may compare the unchanged Experiment 005 Ridge and GBM under exactly three training-memory schemes:

- expanding history,
- trailing 5 calendar years,
- trailing 3 calendar years.

The purpose is not to select a best historical window. It is to ask whether bounded memory specifically repairs the 2022–2024 deterioration while preserving enough earlier-period predictive structure to support an adaptivity interpretation.

Any result remains discovery-contaminated and non-confirmatory.
