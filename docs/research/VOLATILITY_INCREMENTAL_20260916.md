# Matched-input volatility comparison: frozen design

Forecasting only. Core V1, existing engine and all earlier experiments remain
unchanged. No trading, sizing, thresholds or new horizons are explored here.

Use the preceding studies' exact source hashes, panels, daily information times,
24h future realized-variance target and annual expanding-window fits for
2020–2025, starting from 2018 history. All training labels end strictly before
fit time. All compared models share eligible observations. Relative-feature
warmup applies to every model so changing features cannot change the sample.

Six fixed models: raw EWMA, calibrated EWMA, and a 2x2 comparison:
- volatility-only inputs: log recent-24-hour realized variance and log EWMA
  variance (24-hour half-life), identical for linear and boosted models;
- augmented inputs: those two plus the preceding study's five EMA/ATR features,
  identical for linear and boosted models.

Ridge: training-only standardization, alpha 10. Histogram boosting: 80 iterations,
7 leaves, minimum leaf 50, learning rate .05, L2 10, early stopping disabled,
seed 1729. These settings are carried forward without tuning. Each asset and
feature timeframe is fitted separately, with one common 24h target horizon.

Report log-variance MSE and variance QLIKE for every asset/timeframe/year and
full period. Predeclared contrasts isolate architecture within a feature set,
added EMA/ATR information within an architecture, and augmented boosting versus
calibrated EWMA. Positive relative improvement means lower loss. No significance
claim from counts of dependent yearly or asset/timeframe views. No automatic
selection of the best loss function, asset or year after seeing results.

Continue the ML volatility component only if gains are reasonably consistent
across assets/years and both losses relative to strong simple alternatives.
Mixed small gains support keeping the simpler benchmark and closing this
narrow question. Neither outcome establishes profitability or validates an
entire regime engine. All history is previously exposed development data;
causal replay is not a pristine holdout. No deployment or Core changes.

Outputs: every forecast and training cutoff, complete scores, all predeclared
paired comparisons, code/source/data fingerprints and versions. Raw and
calibrated EWMA should reproduce the preceding benchmark study on matched rows.
Run scripts/local/run_volatility_incremental.ps1. PowerShell itself is not
available in the Linux validation environment; its Python entrypoint is.
