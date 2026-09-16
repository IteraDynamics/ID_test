# Isolated regime engine study: frozen design

Core V1 and every existing source file remain unchanged. This branch adds only
research consumers. The original classifier is the frozen benchmark; no trained
model replaces it in Core, and no paper/live runtime is invoked.

## Question and controlled comparisons

Do alternative state representations or ML improve forecasts of subsequent
market behavior, and does any improvement help one fixed trading application?
Eight prespecified comparisons, no parameter search:

1. Constant training outcome mean.
2. Simple standardized ridge: current EMA spread and ATR percentage.
3. Core label: fixed-vocabulary one-hot labels, ridge outcome decoder.
4. Separate trend and absolute volatility: same EMA signs, ATR thresholds and
   expansion rule, retained as independent categorical features; ridge decoder.
5. Relative-volatility priority label: replace absolute thresholds with trailing
   90-day-equivalent observed-bar 25th/75th/90th percentiles, still let volatility
   override trend; ridge decoder.
6. Separate trend and relative volatility: remove that override; ridge decoder.
7. Full standardized ridge: EMA spread, EMA ROC, ATR percentage, ATR acceleration,
   ATR divided by trailing median. Same input columns as boosted model.
8. Histogram gradient boosting: 80 iterations, 7 leaves, minimum leaf size 50,
   learning rate .05, L2 10, no early stopping, seed 1729. No model search.

All ridge decoders use alpha 10 and training-only standardization. The original
engine labels alone are not numerical forecasts; the same trained decoder lets
us compare their predictive information. Decoder fitting is research only.
Binary outputs use squared-loss regression clipped to [0,1]; these are probability
estimates, not established calibrated probabilities. Report Brier score and
mean forecast/outcome for each year and asset. No label accuracy against Core
is used as evidence of improvement.

Relative thresholds use only preceding bars, excluding the current bar. This is
an adaptive deterministic feature, not a fit to future outcomes. A rolling
observed-bar window is not exactly 90 calendar days in the presence of gaps.
No attempt is made to change existing Core gap behavior or EWM initialization.

## Information boundary

Use the two previously hashed BTC/ETH hourly files. Derive 1H and 4H features
separately, preserving the exact original indicator implementation by import.
Forecast at UTC midnight after the preceding bar completes. A common 24-hour
horizon makes outcome definitions comparable across bar durations.

Targets, all measured after the feature timestamp:
- log of the sum of the next 24 squared hourly log returns (variance floor 1e-12).
- Whether any of the next 24 hourly closes is at least 3% below the current
  completed close. This is a close-based adverse excursion, not intrabar lows.
- Whether the next 24-hour return agrees with the current EMA-derived direction.
  FLAT-direction rows have undefined persistence outcomes and are not scored or
  trained for that target. Target direction is common to all compared models.

At Jan 1 of each 2020–2025 evaluation year, fit an expanding window using only
rows whose full target horizon ended strictly before Jan 1. Start with 2018–2019
history. Annual models remain fixed throughout that year. Forecast even where
future outcomes are unavailable; exclude missing outcomes from training/scoring
only. No future missingness screens trading entries. All representations are
scored on a common eligible panel for each target/asset/timeframe.

Features require a complete trailing 240-hour window and valid relative-vol
history. This screen is causal; it cannot erase older gap influence in EWMs.
Daily target windows do not overlap within an asset/timeframe, but observations
remain dependent across days, assets and timeframe views. Do not count those
views as independent replications. No significance or uncertainty claim is
made from raw observation counts.

The entire price history has previously been exposed to research. These are
chronological development replays, not a pristine holdout. No automatic model
selection or deployment follows from the best table entry.

## Fixed practical check

Use the original primary 4H stabilized reversal and 24-hour holding period,
unchanged simulator, cash treatment, initial 50/50 BTC/ETH sleeve allocation,
and all four original cost/delay scenarios. For each model's 4H downside forecast,
permit an otherwise eligible entry only when the latest available daily predicted
risk is no higher than its training prevalence. The forecast must be less than
24 hours old at signal completion. Same rule for every model; threshold is not
selected from test results. Constant forecast serves as the matched forecast-
availability control; unfiltered original is also reported. Models predicting
volatility or persistence do not additionally tune the trading rule.

Forecasts are only potentially usable after observation/feature readiness;
this experiment assumes zero extra feature-feed latency at midnight and retains
one-/two-hour strategy processing delay. No fill at a completed bar's old price.
Accounting and fill replay use the original simulator's checks.

## Decision

Continue only if improvements are consistent across years/assets, exceed simple
controls and remain economically useful after costs. Forecast gains confined to
volatility are not directional alpha. Sparse trade improvements are provisional.
Use the output to identify a narrowly justified next test, not to tune the best
observed model on these same evaluation years and relabel them untouched OOS.

Run scripts/local/run_regime_engine_ml.ps1. Outputs include every timestamped
forecast, training cutoff and latest training label end, yearly forecast scores,
trading metrics, diagnostics, trades and source fingerprints. No market data
is downloaded. PowerShell is inspected only on Linux; Python is executable here.
