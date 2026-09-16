# Volatility benchmark and sizing result

Frozen design commit: 3a9cd8b71b898e4bdd4003a029f9213c2cc569c9.
All results remain chronological development replays on previously exposed
history. Core V1 and existing experiment implementations remain unchanged.

## User reproduction of the preceding engine study

Uploaded regime_engine_ml_20260916T200841_590214Z.zip matches the local prior
study. Source lock and both input hashes agree. Numeric comparisons at rtol
1e-10 / atol 1e-12 pass for all 205,632 predictions, 672 forecast-score rows,
972 trading-summary rows, 108 diagnostics and 2,644 trade rows. The uploaded
Windows environment reports Python 3.12.13, pandas 3.0.2, numpy 2.4.4 and
scikit-learn 1.9.0. The local Python version is 3.12.14.

## Stronger forecast benchmarks

Lower error is better. Full-period log-variance MSE:

| Asset / features | Boosted | Calibrated EWMA | Raw EWMA |
|---|---:|---:|---:|
| BTC / 1H | 0.855 | 0.906 | 0.993 |
| BTC / 4H | 0.881 | 0.906 | 0.993 |
| ETH / 1H | 0.727 | 0.724 | 0.781 |
| ETH / 4H | 0.733 | 0.724 | 0.781 |

Boosting improves on calibrated EWMA for BTC, not ETH, under this loss.
It wins 16/24 asset/timeframe/year comparisons; the comparisons are dependent.
QLIKE gives a different ordering: boosted BTC 4H is 0.569 versus raw EWMA 0.514,
while boosted ETH 4H is 0.431 versus raw EWMA 0.443. Thus the broad claim
"ML is a better volatility model" is not established across assets and losses.
The first study's large gains over a constant forecast overstated the size
of the remaining opportunity beyond a credible adaptive volatility baseline.
No model or half-life was retuned after seeing these results.

This comparison tests the fixed available forecast systems, not architecture in
isolation: the previous boosted model has ATR/EMA features but no explicit
recent-variance or EWMA feature. An incremental test adding those same predictors
to both linear and boosted models remains unperformed. These results do not
establish that nonlinear models cannot add value given stronger inputs.

## Economic result: fixed entry sizing

Base case (30 bps each way), combined BTC/ETH sleeves:

| Sizing | CAGR | Sharpe | Max drawdown | Mean exposure |
|---|---:|---:|---:|---:|
| Full size | 1.43% | 0.172 | -26.04% | 2.69% |
| Fixed half size | 0.78% | 0.145 | -12.89% | 1.33% |
| Raw EWMA | 0.11% | 0.050 | -15.20% | 1.66% |
| Calibrated EWMA | 0.21% | 0.066 | -16.80% | 1.84% |
| Full linear | 0.18% | 0.064 | -18.35% | 1.87% |
| Boosted | -0.22% | 0.011 | -18.64% | 1.82% |

The frozen volatility sizing rule does not improve this reversal mechanism.
Fixed half size has better CAGR, Sharpe and drawdown than any adaptive sizing
variant in the combined base case. This is not a precisely matched-exposure
comparison; each model's resulting exposure is reported explicitly. All variants
have negative combined CAGR under the original 75 bps one-way cost stress.
Do not change the target or add leverage to repair this observed failure.

32 tests passed, including terminal liquidation and multi-trade compounding.
All 64 single-asset sizing replays passed accounting and independent fill replay.
Full weights reproduce original hourly NAV, exposure, fees and turnover for
all asset/scenario runs within 1e-10. 980 protected original files remain
byte-identical. Source differences on this task are confined to new research
files and an additional test in the newly created research test file.
PowerShell was inspected, not executed on Linux; Python full replay completed.

Decision: reject this particular sizing rule for this particular reversal
strategy. Retain the forecast evidence, with calibrated EWMA now a necessary
benchmark. No replacement of Core, promotion, or claim of broadly improved
regime detection is justified. Additional forecast work should test incremental
information with the same strong inputs before making architecture claims.
