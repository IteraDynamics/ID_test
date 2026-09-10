# Options incremental variance research — correction and preparation

Status: IMPLEMENTED PREPARATION; EXPERIMENT DESIGN DRAFT; NO REAL MODEL RESULTS.
This is a new research branch, not a revision of the original negative screen.
No Core, runtime, paper allocation, or trading changes. No paid sources.

## Evidence motivating the correction

Operator supplied dealer_gamma_review_20260910_152124.zip. Its primary report
is SCREEN_NEGATIVE: zero signed continuation gates, three movement gates.
The supplemental sign reversal contradicts the primary dealer-sign story.
The supplied panel has 3,024 rows, starts December 2013, and includes 2025.
All total-gamma labels in 2021--2024 are low. Expanding raw-level terciles
therefore do not supply contemporary within-year comparisons. Within-year
label permutations leave single-state years unchanged. Their pooled p-values
cannot establish incremental out-of-sample usefulness. Overlapping outcomes
and serial dependence further limit day-wise randomization inference.

The existing runner maps observation t to usable t+1 but starts forward returns
at close t. This is not a full-session delay. The new builder explicitly waits
until close t+1 and measures returns ending at closes t+2 through t+6.
Close t+1 is a hypothetical research execution convention, not an achievable
fill guarantee; any subsequent economics must impose executable pricing.

The old report remains valid as a record of its failed prespecified gate.
Do not reclassify it positive, select the reversed sign, or overwrite it.
2025 has already been inspected in this line and is not an untouched holdout.

## Implemented preparation

`scripts/prepare_ml_options_variance.py` reads the long SPY history from
`artifacts/month_end_rebalance_data/SPY_1D.csv` and annual options files from
`artifacts/free_options_history_probe`. Required years are 2008--2024; missing
files fail. The 2025 options file is never opened. Price rows after 2024 are
excluded before returns/targets. Full-source price hashing includes file bytes,
which is provenance rather than use of excluded outcomes.

Required option fields: date, expiration, strike, type, open_interest,
implied_volatility, gamma, delta, bid, ask. No invented replacement columns.
Duplicate contract keys fail. Require finite numeric values, positive strike,
positive open interest and bid, ask >= bid, relative spread <= 50%, IV in
[0.0001, 5] in decimal units, nonnegative gamma, and signed call/put deltas.
Accepted maturities are 7--90 calendar days. Counts of rejected rows are saved.
These thresholds are draft source filters, not optimized trading parameters.

Features:
- Historical mean squared log returns over 5, 21, 63 sessions; 21-session return.
- Near IV: choose expiry nearest 30 days in [21,45], then nearest absolute
  0.5 delta per side within [0.35,0.65]; average both sides. Require both sides.
- Far IV: same rule, expiry nearest 60 days in [46,90].
- Near put-minus-call IV skew at absolute delta 0.25 within [0.15,0.35].
- Far-minus-near IV; actual selected maturities retained.
- Gamma-times-OI strike concentration and <=30-day share across accepted chain.
- Log total gamma standardized against previous 252 SPY sessions (minimum126),
  excluding today's value from the reference statistics. No expanding terciles.

These are vendor-IV delta-selected nearest-expiry proxies, not an interpolated
constant-maturity surface. Gamma-times-OI is not dealer inventory or dollar GEX.
Quote filtering changes the measured chain and requires coverage review.
No historical SPY spot/strike matching is inferred from possibly adjusted closes.

Target: sum of five squared daily log returns after the delayed execution close.
This is a daily-return realized-variance proxy; it misses intraday path variation.
Every fifth SPY session is an anchor; target return intervals do not overlap.
All comparisons will use identical complete anchors. Missing features are not
forward-filled. Daily diagnostics retain missingness and endpoint timestamps.
No label or input beyond December 31, 2024 enters a complete anchor.

Output: daily feature CSV, complete anchor CSV, preparation JSON with input
hashes, CSV hashes, annual coverage, filter counts and stated limitations.
Refuse to overwrite an existing output directory.

## Next experiment, specified before fitting

Question: does options geometry/skew/term information improve next-week variance
forecasts beyond price persistence AND implied volatility?

Use nested inputs: A historical price features; B A plus near IV; C B plus
far IV, skew, term slope and normalized geometry. Compare positive variance
forecasts from regularized log-variance regression and one shallow boosting
model. Scaling, fitting and any log-to-level bias correction use training only.
Near IV squared times 5/252 is an additional explicit benchmark, not assumed
to equal physical expected realized variance.

Proposed annual expanding evaluation 2018--2024, using only rows whose
TARGET END precedes each test year's start. Apply identical eligibility to
all models. This is discovery-contaminated evaluation, never confirmation.
No parameter search, best horizon selection, or reversed dealer-sign rescue.

Before real model fitting, inspect source coverage/units and price adjustment
semantics from the prepared panel. Calibrate the chosen learning procedure
with injected signals on the actual available training features. Specify
plausible effect sizes and evaluate power with dependence preserved; the repo
requires approximately 50% power before a campaign. This draft is not frozen
in its drafting session. Preparation is permitted now and produces no alpha
result. A failing power gate must be reported without pretending a real null.

Primary comparison: C versus B out-of-sample QLIKE (y/p - log(y/p) - 1), with
positive-target handling fixed before fitting. Report yearly loss differences
and paired block uncertainty preserving time dependence; B versus A alone
cannot establish the incremental geometry claim. Proposed screening materiality:
at least 5% mean QLIKE reduction, improvement in a majority of evaluated years,
and a paired 95% block interval excluding no improvement. This threshold still
requires power calibration; it is not a claim of economic value.

Only a surviving forecasting result proceeds to a separately specified SPY/cash
exposure rule, equal-risk comparisons, turnover and executable-cost assessment.
No return, Sharpe, or trading claim follows from forecast accuracy alone.

## Local run

Run the committed PowerShell launcher with the existing data repository as
InputRoot. It uses this branch's code in an isolated worktree and returns one
small ZIP. No data download is attempted. Raw options remain local.

## Verification

Five unit tests cover exact target timing and daily squared-return arithmetic,
future-mutation leakage canary, nonoverlapping anchor intervals, invalid quotes
and duplicate rejection, and delta features with missing-side behavior.
