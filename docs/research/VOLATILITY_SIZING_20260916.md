# Volatility benchmarks and fixed sizing: pre-result design

New research files only on research/regime-engine-ml-20260916. Core and all
previous experiment implementations remain unchanged and are imported read-only.

## Frozen forecast comparison

Same hashed BTC/ETH hourly inputs, 1H/4H feature views, UTC-midnight forecasts,
24-hour variance targets, 2020–2025 annual expanding-window evaluation and
strict label_end < fit_at training maturity as the preceding engine study.
All history remains exposed development data. No hyperparameter search.

Six forecast methods on matched eligible rows:
- Last 24 hourly squared log returns summed (recent24_raw).
- 24 times EWMA hourly squared log returns, half-life 24 hours, adjust=False,
  minimum 240 observations (ewma_raw).
- Each raw benchmark calibrated separately to future log variance using
  training-only StandardScaler + Ridge(alpha=10), refitted annually.
- Prior full linear and boosted models, unchanged predictors/hyperparameters.

Forecasts are in log variance units. Score both log variance MSE and
exp(actual_log_variance - predicted_log_variance) -
(actual_log_variance - predicted_log_variance) - 1 (variance QLIKE).
Exponentiating a conditional log-variance estimate is not an unbiased estimate
of conditional mean variance. No residual smearing correction is fitted here;
QLIKE checks performance in variance units rather than assuming MSE gains
transfer to that scale. Report every asset, timeframe, and year separately.
EWM benchmark skips missing observations; retain the existing causal trailing
240-hour completeness screen and disclose possible influence from older gaps.
No claim that forecast views are independent or that an error improvement is
statistically established from their count.

## Frozen economic check

Use the original primary 4H stabilization / 24-hour reversal trade slots, both
assets, initial 50/50 independent sleeves, all four original cost/delay cases.
No regime filter, new signal thresholds, exit changes, leverage, or compounding
of synthetic rescaled daily returns. Forecasts from 4H only drive sizing.

At signal completion, select the latest daily forecast no more than 24 hours
old (strictly less than 24 hours). Weight at entry is:

min(1, (0.40 / sqrt(365)) / sqrt(exp(predicted log variance))).

40% is a prespecified annualized volatility reference for an active position;
it is not a promised annual portfolio-volatility target for this sparse book.
The position weight is set once, with no within-trade rebalancing. Cash earns
zero as before. Fees apply to actual traded notional. No financing is needed
because risky weight is capped at one. Missing/stale forecast means zero size.

Controls are full-size and fixed 50%-size versions on identical trade slots.
Changing size can change the capital path but never creates new entry slots.
Maintain the original shadow position schedule even after a zero-size trade;
this isolates sizing from signal selection/opportunity effects. Future price
gaps cannot screen entries; the original simulator supplies causal deferred
exit execution times, which the separate sizing ledger replays.

The sizing ledger is new research-only code, not a modification to the original
simulator. Require weight=1 to reproduce the complete original hourly NAV,
exposure, fees and turnover paths; verify fee/cash accounting and independent
fill replay for every alternative. Test zero weights, half weights, terminal
liquidation and missing exits. Compare costs, drawdown, returns and exposure;
reduced drawdown alone is not evidence of intelligent sizing versus less risk.

Outputs: forecasts and yearly scores, full/yearly sizing metrics, diagnostics,
trade and fill ledgers, decision/forecast timestamps and entry weights, daily
NAV/exposure, input fingerprints and Core source lock. No parameter selection
or auto-promotion. PowerShell runner invokes only isolated tests and research.

Decision criteria: forecast gains must beat calibrated simple controls across
more than one asset/year. Economic gains must add something beyond fixed lower
exposure and survive the pre-existing costs/delay checks. An inconclusive result
narrows the research claim; do not repair it with a tuned target or leverage.
