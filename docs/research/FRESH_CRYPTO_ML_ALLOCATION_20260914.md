# Fresh crypto ML allocation experiment — 2026-09-14

## Purpose and status

The operator asked to proceed after reviewing the proposed ML direction. This is a
bounded implementation of `FRESH_CRYPTO_REVIEW_AND_ML_DIRECTION_20260914.md`, using
the exact BTC/ETH inputs from the audited market screen. It tests whether available
information can improve the mixture of two existing portfolios after costs. Prior
charter performance thresholds do not determine this exploratory exercise.

The original trend and allocation endpoints, their 90/180/365-day trend horizons,
60-day covariance, 90/10 diagonal shrinkage, and 20%/40% risk profiles stay fixed.
No Core, runtime, live or paper configuration is imported or changed. No leverage,
shorting, staking, lending, funding model or new coin universe is introduced.

**2020–2024 is development history already inspected in this conversation.** Chronological
model fitting inside that period does not make the research process an untouched OOS
test. No 2025+ price is requested or evaluated. No Monte Carlo or promotion is performed.

## Exact trial budget

| Family | Mixture coefficient: 1 = trend, 0 = allocation | Role |
|---|---|---|
| Trend | Always 1 | Endpoint control |
| Allocation | Always 0 | Endpoint control |
| Fixed blend | Always 0.5 | Static mixture control |
| State rule | Weekly: 1 if average trend agreement <2/3 or fast/slow volatility >1.25; otherwise 0 | Simple state control |
| Constant | Training-target mean passed through the same weekly hurdle as ML | No-feature prediction control |
| Ridge | Regularized linear relative-value forecast | ML candidate |
| Boosted | Shallow gradient-boosted relative-value forecast | ML candidate |

Each family runs at 20% and 40% annual forecast-volatility caps, with exact daily
rebalancing and with a 2-percentage-point total risky-weight no-trade band. Seven
families × two risk profiles × two execution modes = 28 policies. BTC buy-and-hold,
ETH buy-and-hold, a drifting 50/50 buy-and-hold mix, and zero-yield USD cash add four.
**32 policies × four execution scenarios = 128 ledgers**, including eight ML candidates.
The 20% profile is primary; 40% is a declared risk-sensitivity check.

The four scenarios remain frictionless, base 30 bps one way, cost stress 75 bps one way,
and base costs with one additional day of latency. Every scenario uses the same forecasts
trained on base-cost labels. There is no scenario-specific retraining or parameter selection.
The high-cost and extra-delay stresses are separate, not a jointly stressed result.

## Inputs and output identity

The runner accepts the prior completed run directory or ZIP, and reads only its report
and two normalized CSV inputs. Input bytes must match the SHA-256 values below as well
as the source report. Ambiguous original source files and downloads are avoided entirely.

| File | SHA-256 |
|---|---|
| BTC-USD.csv | `9864fb4539fd8199f2c4eab855e7dd8db4aa4e368a5eb670c0f870082a1f58d6` |
| ETH-USD.csv | `993cb7d7b63161181dfa245add3a146fef85a473173038103a8f94de44d4ece5` |

The source report must identify market data and commit
`62cc0f1e110aa4f83e9502198e43105368fbc89e`. Full UTC calendar and OHLCV validation runs
again. History is 2017-01-01 through 2024-12-31. Source vendor/acquisition provenance
remains `operator_local_unverified`; hashing is not a substitute for that evidence.

Code, specification, tests, wrapper and dependency lock must be committed before a
market run. The output records their hashes and actual Python/NumPy/pandas/scikit-learn/
SciPy/threadpoolctl versions. No package or lock update is needed by this implementation.

## Features: fifteen fixed inputs

For bar start t, every feature uses only bars through completed bar t. Its availability
is t+1 UTC midnight. Returns below are simple close-to-close returns. Standard deviation
uses ddof=1. Lookbacks count UTC calendar days, including weekends.

1–6. For each of BTC and ETH, 90/180/365-day price changes divided by 60-day daily
return volatility × square root of the corresponding horizon.

7. Mean across coins of the 14-day return normalized by 20-day volatility minus the
normalized 90-day momentum above.

8. Mean agreement over the six positive-momentum indicators (two coins × three horizons).

9. Mean 20-day daily-return volatility divided by 60-day volatility.

10. Mean share of trailing 60-day squared returns contributed by negative returns.

11. Mean close divided by its trailing 60-close maximum, minus one.

12. Trailing 60-return BTC/ETH correlation.

13. ETH minus BTC 14-day return, divided by trailing 60-day daily spread-return
volatility × sqrt(14).

14. Mean 20-day volume average divided by its 60-day average, minus one.

15. Mean 60-day daily-return volatility × sqrt(365).

Daily-volatility denominators have a fixed 1e-8 floor; squared-return and volume
denominators have 1e-16 and 1e-12 floors respectively. When a coin has essentially zero
variance, correlation is set to zero by definition for the feature. These conventions
handle degenerate fixtures; they do not fill missing source data. All features must be
finite after 365 days of warmup. Current actual holdings enter the execution controller,
not the supervised feature panel, avoiding a model trained on fabricated holdings states.

Feature clipping at training 1st/99th percentiles, means and scales is fitted separately
within every eligible model fit. Those parameters are recorded and applied to future
features. Labels and realized portfolio outcomes are not clipped.

## Counterfactual label and timing

At signal bar t, start each counterfactual with identical unit USD cash at the open of
t+2. Follow either the fixed trend or allocation expert for 14 days, using targets from
t through t+13 at their respective t+2 through t+15 opens. Liquidate everything at
t+16 open. Entry, all interim rebalances and final exit incur 30-bps one-way fees.
The label is log(trend terminal NAV) minus log(allocation terminal NAV). Labels exist
only when the full interval ends inside the pre-2025 input history.

The all-cash initial convention completes the earlier proposal's unspecified common
starting holdings. It produces standardized short-horizon relative-value labels; it
does not reproduce the cost of every possible current inventory state. The actual
portfolio starts once in 2020 and carries inventory continuously; it never resets at
14-day boundaries and never uses label-counterfactual P&L as portfolio P&L.

This label targets relative compounded growth. It is not a maximum-drawdown target,
and its standardized costs need not perfectly forecast costs from the actual current
holdings. That gap is a limitation to inspect, not permission to silently change the
target after evaluating model results.

## Fitting and allocation

Evaluation starts at 2020-01-01 open for every policy. The initial signal is bar
2019-12-30, available 2019-12-31 midnight. Thereafter mixture decisions target Monday
opens, using Saturday's completed bar available Sunday midnight. The model refits at
the first mixture decision associated with each execution quarter. Fits expand through
all training labels whose exit/availability timestamp is **strictly before** the fit's
feature-availability cutoff. At least 500 matured daily labels are required.

For example, a label exiting on 2019-12-31 is not eligible for the initial fit at that
same midnight. A label exiting the preceding midnight can be eligible. A previous
feature window may overlap new feature history, but no training label may consume a
future outcome. All BTC/ETH observations share the same fit/prediction date; they are
not split into independent coin samples. Overlapping 14-day labels remain dependent.

The fixed model configurations are Ridge(alpha=100, solver='svd') and
HistGradientBoostingRegressor(loss='squared_error', learning_rate=0.05, max_iter=50,
max_leaf_nodes=4, max_depth=2, min_samples_leaf=60, l2_regularization=10,
early_stopping=False, random_state=20260914). No random validation split, early stopping,
hyperparameter search, feature selection or winning-seed selection is used. Thread pools
are limited to one during fitting/prediction for predictable execution and replay.

The prior proposal left score calibration open. This implementation instead fixes a
simple hurdle before fitting: h = 0.001 + 0.003 × L1 distance between that day's trend
and allocation target weights. Start at mixture 0.5. If predicted relative log return
exceeds h, select 1; if below -h, select 0; otherwise retain the previous mixture. This
is an explicit turnover-sensitive margin, not a calibrated confidence interval or an
exact forecast of the next switch's fee. It is not charged as an additional ledger cost.
The constant predictor goes through the identical mapping. Coefficients remain fixed
between weekly decisions while the experts' daily volatility-controlled targets update.

Twenty quarters × two profiles × two learned models gives 80 distinct learned fits;
40 constant estimates are controls. Each fit is repeated once for exact within-run
verification, so the full run actually executes 160 learned fits and 80 constant
estimates. Both distinct configurations and repeated execution counts are reported.

Official estimator interfaces: [Ridge](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)
and [HistGradientBoostingRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html).
The implementation was checked against the lock's installed scikit-learn 1.9.0.

## Portfolio accounting and execution band

Targets are the convex mixture of expert weights, including implicit zero-yield USD
cash. Convexity preserves their shared covariance risk cap at target formation. One
continuous self-financing inventory ledger charges actual fees and marks daily wealth.
Every policy uses the same initial capital and final 2024-12-31 open liquidation.
Daily marks do not establish intraday drawdown or opening-fill capacity.

At a proposed execution open, the band compares current risky asset weights with the
lagged target's weights. If their total absolute deviation is below 0.02, it skips the
rebalance. It must execute initial entries, terminal liquidation, a full requested exit,
or a reduction when current weights breach the signal's lagged covariance risk budget.
All current weights are computed from that execution open, and all covariance/target
inputs came from the completed signal bar. This retains the original opening-price fill
proxy; it is not a claim to pre-submit a perfectly sized auction order.

Holding inside the band allows drift. Neither exact nor band mode guarantees a live or
intraday realized-volatility ceiling. The band applies identically to ML and all matched
controls. Stress tests reuse fixed forecasts and mixture decisions; different fees and
delays may still change inventory, skipped orders and realized costs.

## Evidence and interpretation

The ZIP includes the exact normalized inputs and original source report, features,
counterfactual labels with maturity timestamps, every prediction and fit record,
training hashes, preprocessing parameters, mixture decisions, targets and complete
ledgers. It also includes prediction errors, annual returns, 2020–2021/2022–2024 era
metrics, and differences between each learned policy and all five matched controls.
Late-2024 predictions without a complete 14-day outcome remain in the portfolio but
are omitted from prediction-error diagnostics; no future price is fetched to score them.

Labels, model fits/predictions, allocation decisions and ledgers must reproduce exactly
within the run. A deliberately immature-label selection must fail every time. Tests
check counterfactual round-trip fee identities, unchanged expert targets, fixed training
boundaries, future perturbations, planted predictive information, volatility/risk band
overrides, continuous-inventory equivalence with the prior audited engine and packaging.
Synthetic test performance is engineering evidence only.

Compare ML against fixed mixtures and the constant/state controls on identical dates,
risk profiles and execution rules. Then compare exact/band execution to locate any
improvement. A higher gross score or lower exposure alone is not evidence of useful
learning. Inspect annual concentration, costs, delay sensitivity, returns, drawdown,
Sharpe, Calmar, turnover and time underwater. There are only a few independent crypto
cycles despite thousands of rows. No significance or statistical-power claim is made.

## Windows execution

From `C:\Dev\IteraDynamics\ID_fresh_discovery_20260914`, after pulling this research branch:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\run_fresh_crypto_ml.ps1 -SourceRun '.\artifacts\fresh_crypto_20260914_110447_621'
```

The same argument accepts `fresh_crypto_20260914_110447_621.zip` if the directory was
moved or removed. There is no data-root selection or download switch. The wrapper runs
the focused correctness tests, executes the complete development experiment, then prints
the results ZIP to share for review. PowerShell is statically inspected here; actual
Windows execution happens on the operator's machine.
