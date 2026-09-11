# Decision alignment diagnostic — specification before fitting

Date: 2026-09-11. Status: exploratory development experiment, not a promotion test.
Parent review: ML_RESEARCH_REVIEW_20260911.md. Original results remain unchanged.

## Question and fixed design

Do the existing changing daily features contribute useful forecasts beyond each
asset's historical average, and useful allocation decisions after marginal costs?
The alternative is that previous weak economics partly reflected an inconsistent
calendar-week holding horizon and a blanket round-trip gate on retained positions.

Use the exact nine source files from the incremental-information experiment,
verified against its recorded hashes: SPY, QQQ, GLD, IWM, EFA, EEM, IEF, TLT, BIL.
Same daily training panel, features, residual Ridge100 and depth-two GBM, seed17,
annual expanding fits, two preceding inner years for slope calibration clipped
[0,1]. Exactly42 model fits, no hyperparameter/feature/universe search.

Anchor a five-session grid to the first fully feature-supported panel date.
Use this grid for inner validation and outer decisions. Each signal close s
forecasts excess return from open s+1 through open s+6. Adjacent signals differ
by exactly5 source-calendar sessions, including holidays and year boundaries.
Evaluate2018–2024 only. Execute every eligible forecast, liquidate at the last
forecast's label-end open. No same-close fills, no 2025 input or test.

## Decision and execution

Choose weights at signal close using only forecasts, current marked-to-close
holdings, and trailing252 close-return covariance, half diagonal shrinkage.
Full nine-asset covariance is annualized with252 sessions, then multiplied5/252
in the one-horizon objective. BIL forecast excess return is zero.

Maximize mu'w - (3/2) w'Sigma_5 w - c sum_j |w_j - current_j|.
Long-only; risky asset cap25%, total risky cap75%, BIL residual, annual estimated
volatility ceiling10%. Gamma3 is the existing reported CE risk aversion. Costs
are10bps per dollar bought or sold,25bps stress. The myopic objective charges
current incremental trades, assumes continuation after the horizon, and does
not claim dynamic optimality. Final liquidation costs are included in the ledger.
Initial settlement cash has no asset weight; all initial purchases incur costs.
Objective uses pre-fee close weights as an approximation; actual next-open
fees and portfolio wealth use the existing self-financing rebalance accounting.

The feasible incumbent is an explicit no-trade candidate; ties retain shares.
If drift violates decision limits, repair via the same constrained optimizer.
Queue close-time targets for next open. Never use next-open prices to choose
weights. Limits apply to signal-time targets, not guaranteed intraday exposure
or realized risk. A held position may drift; report this limitation.

## Fixed comparisons and economics

Seven forecast variants: historical mean; raw, calibrated, and static-feature
calibrated predictions for each of the two models. The static variants are
negative controls already produced by the existing fitter; they add zero fits.
Run each through (a) this optimizer and (b) the old four-leg cost gate on the
same corrected grid with the same risk ceiling. Controls: periodic risk-limited
equal75 allocation, all-BIL, and no-change buy-and-hold seeded once with the
first risk-limited equal allocation. No-change can subsequently drift beyond
limits; it is a no-action reference, not a constraint-matched optimizer.
17 policies x2 cost scenarios =34 independently reconciled net ledgers.
Additionally replay the17 cost10 order paths at zero fees and25bps without
reoptimizing:34 matched-order sensitivity ledgers, zero extra model fits.
No-trade actions remain no-trade during these replays.

Report CAGR, annualized mean/volatility/CE (252 mean - 3/2*252 variance),
maximum drawdown, turnover, exposure, yearly/ex2020 CE and forecast MSE skill.
Ex2020 CE is a descriptive pooled-moment check, not a continuous investment path.
Report gross through the matched-order zero-fee replay, not a free-cost optimizer.
Historical data have been repeatedly inspected: all conclusions descriptive.

## Decision rule fixed before results

Primary calibrated model must beat the identically optimized historical mean
and its static-feature control in pooled and ex2020 MSE, with mean MSE gains in
at least4/7 years. It must exceed optimized mean, periodic equal, BIL and
no-change in all-period and ex2020 net CE at10bps and25bps; at least4/7 annual
CE gains against optimized mean at10bps. Matched-order25bps must also beat
matched-order controls in all/ex2020 CE. These are descriptive consistency
criteria, not significance or a quantified power claim. Report raw forecasts
and all failed criteria, not just the best result. A raw-only improvement earns
at most a narrowly stated calibration finding, not a silent change of primary.
If neither model passes, close this daily-summary/five-session ETF design as
an alpha candidate. Do not launch another model or threshold search in response.

## Mechanical gates

Before market fits, test five-session labels on a holiday calendar, marginal
no-trade behavior, known optimum, constraints, initial costs, self-financing
ledger, future-open independence, and training label maturity. Record numerical
solver failures, feasibility and objective gaps; fail loudly, no hidden fallback.
Archive specification hash before fits, code/source/environment identity,
fit and calibration boundaries, forecasts, decisions, daily ledgers and hashes.
