# ML Lab Experiment 012 — Compact macro-interaction simplification

**Specification date:** 2026-09-04

**Status:** SPECIFICATION_FROZEN — NOT_IMPLEMENTED / NOT_RUN

**Branch:** `agent/ml-lab-exploration-20260903`

**Evidence boundary:** EXPLORATORY / DISCOVERY-CONTAMINATED / NON-CONFIRMATORY

## Purpose and scope of this transition

Can one compact, interpretable interaction model reproduce the original U.S.
macro-GBM benefit with stable chronological performance?

The operator authorized documenting Experiment 011 and specifying this bounded
follow-up before more fitting. This transition creates documentation and input
fingerprints only. It does not implement a runner, fit a model, or generate an
Experiment 012 result. Implementation, synthetic verification, and any real run
are subsequent work, not represented here as already performed.

Experiment 011 is closed as an exploratory transfer failure. This test uses only
the original U.S. universe and cannot rescue that transfer result. It is governed
by the [ML Lab charter](ML_LAB_EXPLORATION_CHARTER.md), separate from Campaign #58.
Campaign #58's binding power failure and its restrictions are unchanged.

## Why this differs from Experiment 009

Experiment 009 already tested a 32-feature macro Ridge, including all 16 macro
interaction products; that model is not a new candidate. Experiment 012 tests one
smaller fixed block of six recurring interactions, retaining the same main effects
and Ridge regularization. It asks whether removing the other ten interactions
makes the existing U.S. structure easier to express and interpret.

The six interactions are exactly those explicitly listed as prominent recurring
interactions in [Experiment 009's results](ML_LAB_EXPERIMENT_009_RESULTS.md).
[Experiment 010](ML_LAB_EXPERIMENT_010_RESULTS.md) provides mechanism/recurrence
context. The choice therefore uses already-inspected discovery evidence and is
not independent feature selection. No new importance ranking or outcome scan was
performed to select this block. Failure will not trigger a search over subsets.

## Frozen data, universe, and target

Use exactly the original 14 U.S. ETFs, in this order:

`RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY`.

Inputs are the existing 14 `data/{ticker}_1D.csv` files and these Experiment 009
artifacts:

- `artifacts/ml_lab_experiment_009/experiment_009_oos_predictions.csv`;
- `artifacts/ml_lab_experiment_009/experiment_009_anchor_metrics.csv`;
- `artifacts/ml_lab_experiment_009/experiment_009_macro_state.csv`.

The [input manifest](evidence/ML_LAB_EXPERIMENT_012_INPUT_MANIFEST.json) freezes their
SHA-256 hashes and byte sizes. Read existing files only; no acquisition, refresh,
substitution, country-ETF data, or new macro series. A mismatch stops execution
pending an explicit, documented input-version decision. Hashing an input file
does not authorize use of any observations after the cutoff.

Reuse the Experiment 005 panel definition as of commit
`e512ee7ef1ec2535f59f6dec38a3069fc6b9eaf3`: five-common-session anchors, 20-session
forward returns divided by trailing 60-session realized volatility times sqrt(20),
then percentile-ranked across the frozen U.S. cross-section. Preserve the existing
120-session feature warmup, complete-row rules, feature formulas, and ranking tie
method. Exclude observations after 2024-12-31 before computing features or targets;
no target may end after that date. The reserved 2025 holdout remains untouched.

## Exactly one new model

Candidate name: `compact_macro_ridge`.

Estimator: `Pipeline([StandardScaler(), Ridge(alpha=10.0)])`, using the same
estimator defaults as Experiment 009's Ridge in the recorded execution environment.
Record Python, NumPy, pandas, SciPy, and scikit-learn versions. Scaling is fitted
only on each fold's training rows. No feature selection, coefficient sign
constraint, regularization search, clipping, discretization, or alternate model.

Fixed feature order:

1. All 12 `exp9.PRICE_FEATURES`, unchanged and in their existing order.
2. The four `exp9.MACRO_STATES`, unchanged and in their existing order:
   `rate2_pct252`, `curve_10y2y_pct252`, `rate2_chg20`, `vix_pct252`.
3. These six existing interaction columns, in this exact order:

| Column | Interpretation |
|---|---|
| `curve_10y2y_pct252__x__vol_60d_xrank` | Curve state × relative volatility |
| `vix_pct252__x__vol_60d_xrank` | VIX state × relative volatility |
| `curve_10y2y_pct252__x__ret_120d_xrank` | Curve state × relative momentum |
| `rate2_pct252__x__vol_60d_xrank` | Rate state × relative volatility |
| `rate2_pct252__x__ret_120d_xrank` | Rate state × relative momentum |
| `rate2_chg20__x__ret_120d_xrank` | Rate change × relative momentum |

Total: 22 features. Preserve the four macro main effects for consistency with the
existing full model and interaction parents. They are common to all ETFs at an
anchor, so their additive contribution alone does not change within-anchor ranks.
The interaction products are formed in the original feature units before scaling,
exactly as in Experiment 009. Feature order and count must be asserted.

## Folds, support, and fixed comparisons

- Use Experiment 009's annual test years and identical per-fold test rows; do not
  choose a start year after seeing Experiment 012 results.
- Reuse the strict training embargo: both timestamp and target-end date must be
  before the first test anchor of that year.
- Retain exactly `expanding` and `trailing_3y`; trailing memory applies the existing
  three-calendar-year lower bound to training timestamps.
- Preserve at least 1,000 training rows and 50 distinct training anchors.
- Primary memory is `trailing_3y`, inherited from Experiment 009. Expanding is the
  fixed robustness comparison, not an alternative selected if the primary fails.
- Calendar summaries: all evaluated years, pre-2022, and 2022–2024. Use identical
  anchor sets for every paired comparison.

Comparators are all four saved Experiment 009 models: `price_ridge`, `price_gbm`,
`macro_ridge`, and `macro_gbm`. Do not retune or replace them. Rebuild the original
32-feature U.S. panel and verify row keys, target values, and fold support against
the saved artifacts before fitting the one new candidate. No silent inner-join
losses, missing-model cells, duplicate keys, or changed eligible folds are allowed.
Numerical target comparisons use the existing `1e-10` absolute parity tolerance;
dates, row keys, and counts must match exactly. Missing or non-finite required data
fail closed. Validate saved anchor metrics by recomputing them from saved scores
with Experiment 009's metric routines before accepting them as references.

## Measurements

Use Experiment 009's metric definitions and tie handling, for the candidate and
all comparators. At each test anchor report rank IC and top-minus-bottom raw target
spread; summarize mean, median, positive-IC fraction, anchor count, and annual
results. Spreads are volatility-adjusted target units, not trading returns.

Primary incremental comparison: compact macro Ridge minus price Ridge. Also report
compact minus full macro Ridge, compact minus macro GBM, and compact minus price
GBM. Use paired anchor differences, not differences between mismatched samples.
Report yearly differences for every evaluated year; no best-year subset.

Report rank correlation between compact and macro-GBM scores at each anchor as a
descriptive fidelity measure. Similar scores do not establish predictive value;
predictive increments against the realized target remain the deciding measures.
Do not use a transfer/retention ratio with a zero or negative reference increment.
No ratio threshold is used in the disposition below.

## Interpretable model record

Save all fold coefficients, scaler means/scales, intercepts, and ordered feature
names. Convert standardized coefficients back to original-feature score units:
`raw_coefficient[j] = coefficient[j] / scaler.scale_[j]`; adjust the intercept by
subtracting `sum(raw_coefficient * scaler.mean_)`.

For `vol_60d_xrank` and `ret_120d_xrank`, report the effective slope at each test
anchor as its raw main-effect coefficient plus the sum of the corresponding raw
interaction coefficients times the contemporaneous macro states. These are slopes
of the fitted score, not causal economic effects. Show how their signs and sizes
vary across annual folds and the existing Experiment 010 regime definitions.
Do not create new regime cuts or select coefficients based on test outcomes.

This distinguishes a stable conditional relationship from a pooled coefficient
average that hides repeated reversals. Feature importance alone is not a mechanism.

## Frozen descriptive disposition

These rules guide this exploratory follow-up; they are not statistical significance
tests or promotion gates. Equality does not satisfy a strictly positive condition.

Define stable baseline lift for a memory scheme as all of:

1. compact-minus-price-Ridge mean IC and mean spread are strictly positive in both
   pre-2022 and 2022–2024;
2. compact-minus-price-Ridge annual mean IC is positive in strictly more than half
   of the evaluated test years;
3. the compact model's own mean IC and mean spread are positive in both periods.

Define full-sample GBM matching as compact mean IC >= macro-GBM mean IC and compact
mean spread >= macro-GBM mean spread, on the same full-sample anchors for that memory.

- If primary trailing-3y stable baseline lift fails:
  `NO_STABLE_PRIMARY_SIMPLIFICATION`. Report any favorable expanding outcome as
  secondary/memory-dependent; it does not replace the primary result.
- If primary stable lift passes but either expanding stable lift or GBM matching
  in either memory fails: `PARTIAL_OR_MEMORY_DEPENDENT_SIMPLIFICATION`.
- Only if stable lift and full-sample GBM matching pass in both memories:
  `EXPLORATORY_COMPACT_REPRESENTATION_SUPPORTED`.

Publish every component and every cell, including negative ones. Report
coefficient-direction instability even if numerical performance rules pass.
None of these labels establishes a causal mechanism, independent validation, or
international portability. Overlapping forward windows invalidate an assumption
that weekly anchors are independent; no naive independent-observation p-values.

## Required implementation checks and artifacts

Before any real Experiment 012 fitting, synthetic tests must cover exact feature
order/count, training-only scaling, target-end embargo, the 2024 cutoff, missing
inputs, duplicate keys, reference-parity failures, and every disposition branch.
The full runner must complete twice on synthetic inputs with identical outputs.
All metrics and coefficients must be finite; serialization must support NumPy /
pandas scalars without changing values. Unexpected failures stop the run.

Expected directory: `artifacts/ml_lab_experiment_012/`. Required outputs:

- `experiment_012_report.json`: status, frozen design, input hashes, code/environment
  versions, boundary flags, support/parity results, all disposition components;
- `experiment_012_oos_predictions.csv`: timestamp, ticker, test year, memory, model,
  target-end date, target raw/rank, score;
- `experiment_012_anchor_metrics.csv` and `experiment_012_yearly_metrics.csv`;
- `experiment_012_comparison_summary.csv`: all fixed comparisons, memories, periods;
- `experiment_012_fold_support.csv` and `experiment_012_reference_parity.csv`;
- `experiment_012_coefficients.csv`: coefficients and scaler parameters by fold;
- `experiment_012_effective_slopes.csv`: the two specified conditional slopes;
- `experiment_012_score_fidelity.csv`: compact versus macro-GBM rank agreement.

Do not emit a successful result report until every required check and output
completes. Input or integrity failures are execution failures, not negative
research findings. If the primary candidate fails, park this six-interaction
simplification; do not add interactions, change alpha, swap memories, or try a
different target within 012. A negative result does not disprove every possible
simple representation.

## Standing boundaries

No destination-country fit or reuse as a fresh holdout; no 2025 reserved holdout
use; no Core v1/v2, runtime, strategy, threshold, order, execution, NAV, exposure,
portfolio, paper/live, or capital change. A favorable exploratory result would
require a separate governed confirmation design before any promotion claim.
