# Initial isolated engine study result

Decision: continue research specifically on volatility prediction; do not
promote a new directional engine or trading strategy from this experiment.
No Core source, thresholds, configuration or runtime behavior changed.

Frozen design: 4afa21d6c66c6cbcbab6b155f167c644570bf4dc.
24 tests passed. Full 2020–2025 annual expanding-window replay completed for
BTC/ETH at 1H/4H, all eight models, all three targets. All 72 single-asset
practical simulations passed existing accounting/fill replay checks. The
unfiltered primary reproduces prior CAGR, Sharpe and drawdown for every
scenario, asset and period within 1e-12. All 980 protected original files are
byte-identical; branch changes add new files only. PowerShell not run on Linux.

## Observed forecast evidence

Skill is 1 minus model squared error divided by the matched training-mean
forecast squared error. These are forecast-error reductions, not investment
returns. Core-label results include a training-only ridge outcome decoder.

| Target/model | BTC 1H | BTC 4H | ETH 1H | ETH 4H |
|---|---:|---:|---:|---:|
| Log variance, Core label | 23.4% | 30.2% | 30.2% | 35.4% |
| Log variance, full linear | 37.1% | 38.5% | 41.4% | 43.0% |
| Log variance, boosted | 43.5% | 41.8% | 46.1% | 45.7% |
| Downside Brier, full linear | 6.3% | 7.5% | 7.4% | 7.5% |
| Downside Brier, boosted | 5.2% | 5.0% | 5.9% | 6.5% |

Boosting beats the full linear volatility model in 19/24 asset/timeframe/year
comparisons; these views are dependent, not 24 independent confirmations.
It beats that linear model for downside in only 6/24, persistence in 3/24.
Boosted persistence skill versus constant is negative in all four full-period
asset/timeframe views (about -2% to -3%). Simple-linear persistence gains where
positive are tiny (under 0.3%). No convincing directional-persistence evidence.

Separating trend/absolute-volatility labels changes little. Relative-threshold
representations perform worse on volatility and downside in this initial
comparison. The original timeframe imbalance alone was not evidence that
normalizing the thresholds would improve outcome forecasts. Continuous inputs
retain more predictive information than these discrete representations here.
No uncertainty intervals or formal significance claim have been established.

## Fixed trading application

The daily 4H downside forecast gates the original 24-hour reversal entry using
a fixed training-prevalence threshold. It does not use predicted volatility
for sizing, so it cannot adjudicate the economic value of volatility forecasts.

| Base case, combined sleeves | CAGR | Sharpe | Max drawdown |
|---|---:|---:|---:|
| Unfiltered / constant control | 1.43% | 0.172 | -26.04% |
| Full linear downside filter | 1.60% | 0.262 | -12.87% |
| Boosted downside filter | -2.76% | -0.344 | -28.03% |

All tested practical versions have negative combined CAGR at 75 bps each way.
The 30 bps base case has 71 full-linear trades, 70 boosted trades, 115 original
trades. These outcomes do not justify tuning the risk threshold post hoc.
Previously exposed history remains development data despite causal refits.

Next discriminating test, not performed here: benchmark the volatility forecaster
against direct recent-variance/EWMA forecasts with training-only calibration,
then test one predefined position-sizing application if the incremental gain
persists. Do not infer profitability from the current log-variance MSE gain.
The original Core engine remains the frozen production incumbent.

All model/year scores and trading summaries are retained under
`docs/research/evidence/regime_engine_ml_20260916/`. The local runner ZIP also
contains every forecast with its fit time and latest training-label end.
