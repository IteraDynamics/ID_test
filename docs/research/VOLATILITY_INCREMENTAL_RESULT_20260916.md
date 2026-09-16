# Matched-input result: retain simple forecasting benchmark

Decision: close this fixed-model comparison without promoting boosted ML or
changing Core. Retain augmented ridge as a research volatility benchmark; its
incremental feature information is modest and economic value remains untested.
Do not infer a stronger standalone regime engine or profitable trading strategy.

Frozen design: 1213642eda5d9c7b66f8dc7663d7aa4a787b0107.
Nine new tests pass. Full annual chronological replay completed for all models,
assets and timeframes. Raw/calibrated EWMA scores reproduce the preceding study
within 1e-12 for every year/view. All 980 protected original files remain
byte-identical. No existing source file changed. No trading or sizing rerun.

Full-period log-variance MSE (lower is better):

| Asset / feature timeframe | Linear volatility inputs | Linear augmented | Boosted augmented |
|---|---:|---:|---:|
| BTC / 1H | 0.8959 | 0.8676 | 0.8516 |
| BTC / 4H | 0.8959 | 0.8822 | 0.8794 |
| ETH / 1H | 0.7213 | 0.6931 | 0.7140 |
| ETH / 4H | 0.7213 | 0.7066 | 0.7324 |

With identical augmented inputs, boosting beats ridge in 13/24 yearly
asset/timeframe comparisons for log-variance MSE and 14/24 for QLIKE. With only
the two volatility inputs, boosting wins 4/24 and 10/24 respectively. There is
no stable nonlinear-model advantage under this fixed specification.

Adding EMA/ATR predictors to ridge improves full-period MSE and QLIKE in all
four views. Its annual improvement count is 19/24 for MSE and 15/24 for QLIKE.
Full-period MSE gains are approximately 1.5–3.9% relative to the two-input ridge.
These dependent comparisons are descriptive, not independent confirmations or
formal statistical evidence. Both one-hour and four-hour views predict the same
next-day outcome. No confidence interval or corrected significance is claimed.

Loss choice matters. For BTC 4H, raw EWMA QLIKE is 0.5143, versus augmented ridge
0.5466 and augmented boosting 0.5657, despite raw EWMA's worse log-variance MSE.
The exponentiated log forecast is not asserted to be an unbiased mean-variance
forecast. Do not choose whichever loss favors a model after observing results.

The limited positive result is incremental predictive information in the
continuous features under a simple model. It is not a reason for more broad ML
search, and this experiment supplies no new evidence on returns or direction.
All history remains previously exposed development data, not a pristine holdout.
Future use would require a separately defined decision problem and untouched
forward evaluation; no automatic promotion is authorized or implemented.

All scores and predeclared contrasts are stored under
`docs/research/evidence/volatility_incremental_20260916/`. The local ZIP also
contains every forecast with training timestamps. Python ran successfully;
PowerShell wrapper was inspected only in this Linux environment.
