# ML development program — authorized exploratory engineering

2026-09-10. The operator requested a substantive ML development program modeled
on professional quantitative research. This authorizes bounded development and
comparisons, not a claim that Itera reproduces any firm's proprietary process.
This document is the living development record. Prior negative experiments stay
closed. This is a new research process and return target, informed by those
results, not an untouched independent test of the old hypothesis.

## Research question and economic use

Can shared models learn conditional five-session ETF returns from ordered price
and volume observations, beyond engineered trend/volatility summaries and
historical-return baselines? Weekly allocation is the downstream decision.
Predict next-session open to the open five sessions later. The open-to-open
label matches a five-session holding decision; it is not crash probability.
The first deliverable is a prediction development harness. Risk estimation,
portfolio construction and execution are subsequent modules, not implied by a
positive forecast metric. Do not map forecasts mechanically into unreviewed
portfolio weights.

Weak mechanism prior: gradual allocation and risk-budget adjustments can make
price response depend on the recent joint path of returns, volume and volatility.
These inputs do not identify actual compelled flows. Learning a stable empirical
relationship is useful discovery; a mechanism remains to be established before
promotion. Simple models may capture all available information.

Long-only U.S.-listed ETF research, adjusted synthetic units. No HFT claims.
Actual brokerage tradeability and a new system's runtime cadence remain unverified;
this work is offline engineering and prediction development, not execution.
Five sessions is the development horizon; a future allocation study must include
an extra-session delay and actual turnover/cost assumptions. Core is frozen.

## Data and split ownership

Use existing SPY, QQQ, GLD files to exercise the complete development pipeline.
These three are the initial testbed, not a claim of sufficient independent breadth.
Pre-2025 source data only, beginning 2013-12-02; 200 prior closes for summaries,
20 ordered observations for sequence inputs. Preserve the matching adjustment
manifests and source hashes. No silent intersection of missing ETF sessions.

2018–2024 have been inspected. All resulting metrics are development diagnostics.
Annual development validation blocks: 2018, 2019, 2020, 2021, 2022, 2023, 2024.
Within each outer year Y, use Y-2 and Y-1 as the inner validation years, retaining
only training labels ending strictly before the first validation signal. Inner
folds need at least 252 distinct training dates; unsupported folds fail explicitly.
Selection uses mean squared forecast error across inner validation observations.
The outer year is excluded from selection and early stopping. Once evaluated it
becomes part of the recorded development history, not a fresh confirmation set.
Scalers fit on each training fold only. Weekly validation uses the last observed
session of each ISO week; daily training pools the ETFs. Dates are correlated and
labels overlap; row count is not an independence or power claim.

2025 is reserved by Campaign #50 and cannot be reassigned here. No final untouched
evaluation period is currently authorized. Do not manufacture one by renaming a
previously observed year. A selected candidate needs a separate confirmation
proposal after the development evidence is reviewed.

## Version 1 bounded model set

Model targets are simple return in percentage-point units for numerical conditioning;
outputs are converted back to return fractions. No target winsorization.

- Two controls: zero expected return; per-ETF training mean return.
- Ridge alpha 1 and 100 on engineered summaries.
- Histogram GBM depth 2 and 3: 100 iterations, learning rate .05,
  minimum leaf 100, L2 10, early stopping disabled, seed 17.
- Feedforward neural net on summaries: hidden widths (16) or (32,16),
  ReLU, Adam, L2 alpha .1, learning rate .001, 150 iterations,
  batch 128, shuffle=False, no random early-stopping split, seed 17.
- Ordered-window neural net: same two architectures, consuming flattened ordered
  20-session return and relative-volume sequences, plus fixed ETF identity.
  This is an ordinary MLP over lagged inputs, not a transformer, recurrent net,
  convolutional architecture or automatic claim of temporal representation quality.

Eight candidates, seven outer years, two inner folds plus one outer refit:
168 fits maximum for the main model comparison. Up to 56 additional fits only
for two declared learning-curve sizes and two alternative seeds of the selected
candidate in each outer year. These diagnostics cannot change candidate selection.
Full seed/learning-curve work is deferred until model-comparison artifacts are
reviewed; version 1 implements the comparison and training-error diagnosis.
No additional search hidden in seeds, outcome thresholds, universes or costs.
A one-session implementation/check budget; broader study needs a recorded update.

Summary inputs: returns 5/20/60, price/SMA200 minus one, volatility 20/60,
60-session drawdown, negative-return fraction 20, and three ETF identity flags.
Sequence inputs: daily returns and volume divided by its past-inclusive 60-session
mean minus one, ordered oldest to newest, and the same identity flags. Current
session data becomes available only after close. Summary vs sequence changes
both representation and volume information: do not attribute differences solely
to sequence learning. A matched-information ablation is required before that claim.

## Required outputs and interpretation

All candidate inner-fold scores, selected candidate per year, convergence warnings,
training/validation errors, OOS development forecasts, annual/asset forecast MSE,
MAE and correlation, baseline comparisons, source/code/output hashes. Keep losing
candidates visible. Iteration-limit warnings are recorded, never silently retrained
with extra iterations. Nonfinite predictions fail. Low training error with poor
validation suggests overfitting; persistent errors alone do not identify its cause.

Version 1 has no economic pass/fail verdict. Its status is
DEVELOPMENT_DIAGNOSTIC_ONLY. Useful forecasts must later survive portfolio
construction, risk estimation, costs and governed independent confirmation.
No annual validation score licenses capital, a sleeve, or a production rollout.

## Professional practice adapted, not proprietary imitation

We borrow separation of data engineering, feature/representation research,
chronological model selection, economic decision design and final evaluation.
Jane Street publicly describes neural models, model tuning and production-trade
analysis; Two Sigma describes dedicated data and feature research teams. Neither
public source establishes our exact model set or validation calendar as theirs.
Sources checked 2026-09-09:
https://www.janestreet.com/join-jane-street/machine-learning/
https://www.twosigma.com/

## Next modules after first diagnostic run

1. Inspect error/selection stability, then run the already bounded learning curves
   and seed checks. Add a matched-information representation ablation only through
   an explicit development revision, recorded before its results.
2. Decide whether available instrument breadth and information justify a larger
   dataset. Audit existing files before requesting downloads; no subscription.
3. Separate expected-return forecasting from covariance/risk forecasts. Design
   constrained portfolio construction with turnover penalties and cash returns;
   compare the same optimizer with learned and baseline forecasts.
4. Only if development supports a candidate, freeze the complete selection and
   trading procedure and propose genuinely independent evaluation.

## Implementation correction recorded before repair run

The first 168-fit run is INVALID and excluded from conclusions: the last inner
validation labels could cross the next outer year's first signal. All inner
validation label ends must be strictly before that outer first signal, in
addition to purging each training fold against its own validation boundary.
Added a test that explicitly demonstrates and rejects this New Year crossing.
One 168-fit correctness repair is recorded; no performance-driven settings
change. Preserve the invalid report/source and do not reset the experiment count.
