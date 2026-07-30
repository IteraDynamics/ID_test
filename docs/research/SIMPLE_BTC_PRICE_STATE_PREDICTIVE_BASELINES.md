# Campaign #48 — Simple BTC Price-State Predictive Baselines

## Status

**DRAFT GOVERNING SPECIFICATION — no predictive outcomes may be generated, calculated, viewed, inspected, ranked, or interpreted until this document is separately reviewed and frozen by commit.**

Campaign #48 is research-only, observation-only, deterministic, replay-safe, chronological, leakage-safe, and fail-closed.

It does not authorize any runtime, regime, threshold, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Plain-English question

Campaign #48 asks:

> Does BTC's recent price behavior contain reliable information about what happens next?

The purpose is to establish a transparent predictive baseline before Itera attributes value to regimes, transitions, machine learning, or more complicated signal logic.

This campaign is not a trading-strategy backtest. It is a prespecified statistical discovery study over simple BTC price-state features.

## Research objective

Determine whether a small, finite, interpretable set of BTC price-state predictors contains reproducible information about future:

- directional return;
- absolute return magnitude;
- realized volatility;

at exact 24-hour, 72-hour, and 168-hour horizons.

A supported association remains a research finding only. It does not establish deployable alpha, portfolio value, economic usefulness, or strategy fitness.

## Governed source

The only authorized market source is:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- byte count: `4,792,028`;
- rows: `70,069`;
- first timestamp: `2018-01-01 00:00:00`;
- last timestamp: `2025-12-31 00:00:00`;
- cadence: exact hourly observations.

The implementation must fail closed if the path, digest, byte count, row count, schema, ordering, timestamp uniqueness, or timestamp cadence does not reconcile exactly.

No source substitution, downloading, interpolation, filling, resampling, nearest-row matching, as-of matching, synthetic bars, or timestamp repair is permitted.

## Required source fields

The source must provide the exact fields needed to identify:

- timestamp;
- close price.

Any additional source columns may be preserved for source reconciliation but may not enter Campaign #48 predictors or outcomes unless this specification is amended and refrozen before outcome generation.

Close prices must be finite and strictly positive.

## Anchor construction

Campaign #48 uses one common deterministic 168-hour anchor grid so that all maximum-horizon outcomes are non-overlapping across adjacent anchors.

The anchor origin is the earliest source timestamp for which:

- every exact hourly close required for the trailing 168-hour predictor window exists;
- the current close exists;
- the timestamp lies on the governed source sequence.

Starting from that origin, anchors advance in exact 168-hour increments.

An anchor is retained in the anchor inventory when all eight predictors can be computed. Outcome availability is recorded separately by family and horizon.

A scheduled anchor timestamp that is absent from the source is not shifted or replaced. The implementation must fail closed on a broken governed hourly sequence rather than silently alter the grid.

## Chronological partitions

The common anchor inventory is divided into three contiguous, near-equal chronological partitions.

If the anchor count is not divisible by three, remainder anchors are assigned to earlier partitions in chronological order.

Required evaluations:

1. partition 1 is the development sample for partition-2 evaluation;
2. partitions 1 and 2 together are the development sample for partition-3 evaluation;
3. all complete anchors form the pooled fit.

No random split, shuffle, cross-sectional fold, bootstrap split, or future-informed preprocessing is permitted.

## Frozen predictor inventory

Campaign #48 contains exactly eight simple predictors.

Let `C_t` denote the close at anchor timestamp `t`. Let hourly log return be:

`r_u = ln(C_u / C_{u-1})`.

### 1. Trailing 24-hour log return

`return_trailing_24h = ln(C_t / C_{t-24h})`

### 2. Trailing 72-hour log return

`return_trailing_72h = ln(C_t / C_{t-72h})`

### 3. Trailing 168-hour log return

`return_trailing_168h = ln(C_t / C_{t-168h})`

### 4. Trailing 24-hour realized volatility

`realized_volatility_trailing_24h = sqrt(sum(r_u^2))`

using every exact hourly return with endpoint timestamps in `(t-24h, t]`.

No annualization is applied.

### 5. Trailing 168-hour realized volatility

`realized_volatility_trailing_168h = sqrt(sum(r_u^2))`

using every exact hourly return with endpoint timestamps in `(t-168h, t]`.

No annualization is applied.

### 6. Distance from trailing 168-hour close mean

Let `mean_168h` be the arithmetic mean of closes at exact hourly timestamps in `[t-168h, t]`.

`distance_from_mean_trailing_168h = (C_t / mean_168h) - 1`

### 7. Position within trailing 168-hour range

Let `low_168h` and `high_168h` be the minimum and maximum closes at exact hourly timestamps in `[t-168h, t]`.

`range_position_trailing_168h = (C_t - low_168h) / (high_168h - low_168h)`

If `high_168h == low_168h`, the predictor is unavailable for that anchor. No substitute value is permitted.

### 8. Drawdown from trailing 168-hour high

`drawdown_from_high_trailing_168h = (C_t / high_168h) - 1`

## Predictor boundary

No additional indicators, thresholds, bins, labels, interactions, ratios, splines, polynomial terms, moving-average crossovers, oscillator names, technical-analysis pattern names, learned features, or data-dependent feature selection are authorized.

The three return windows are separate prespecified candidates. The two volatility windows are separate prespecified candidates. The three 168-hour price-location predictors are also separate prespecified candidates despite expected correlation.

Correlation does not authorize dropping, combining, or replacing a candidate after outcomes are inspected.

## Frozen outcomes

Let horizon `h` be one of `24`, `72`, or `168` hours.

All outcomes require exact source timestamps. A missing required timestamp or hourly interval makes that outcome unavailable for the anchor.

### Family R — directional forward log return

`forward_return_h = ln(C_{t+h} / C_t)`

This is a continuous signed outcome. Campaign #48 does not create a separate binary up/down label.

### Family M — absolute forward return

`forward_absolute_return_h = abs(forward_return_h)`

### Family V — forward realized volatility

`forward_realized_volatility_h = sqrt(sum(r_u^2))`

using every exact hourly return with endpoint timestamps in `(t, t+h]`.

No annualization is applied.

## Candidate family

The frozen candidate inventory is:

- 8 predictors;
- 3 outcome families;
- 3 horizons;
- 72 total predictor-outcome-horizon candidates.

Every candidate must remain visible in canonical results, including null, missing, failed, rank-deficient, nonfinite, insufficient-support, and otherwise unrankable candidates.

## Estimator

Each candidate is evaluated with ordinary least squares containing:

- an intercept;
- exactly one standardized structural predictor;
- no regime labels;
- no regime fixed effects;
- no additional price controls;
- no interactions.

HC3 heteroskedasticity-consistent covariance is required.

Reported inferential quantities are:

- coefficient on the standardized predictor;
- HC3 standard error;
- two-sided normal p-value;
- 95% normal confidence interval.

No alternate estimator may be substituted after outcomes are inspected.

## Development-only standardization

For partition-2 evaluation, the predictor mean and standard deviation are computed from complete partition-1 development rows only.

For partition-3 evaluation, the predictor mean and standard deviation are computed from complete development rows in partitions 1 and 2 only.

The corresponding evaluation predictor is transformed using those development statistics.

For the pooled fit, pooled complete rows define the pooled mean and standard deviation.

The implementation must fail closed for a candidate fit if the applicable development predictor is nonfinite or has zero standard deviation.

Outcomes are not standardized.

## Fit interpretation

Campaign #48 is an association-discovery design.

For chronological evaluation fits, preprocessing parameters come only from prior development rows, while the coefficient and HC3 inference are estimated on the applicable evaluation partition.

The campaign does not select hyperparameters, refit a production forecast, calculate trading positions, or convert coefficients into signals.

## Support and rankability gates

A candidate is rankable only when all of the following hold:

- at least 90 complete pooled anchors;
- at least 25 complete anchors in each chronological partition;
- finite predictor and outcome values;
- nonconstant development predictor for each chronological evaluation;
- full-column-rank design for pooled, partition-2, and partition-3 fits;
- finite nonzero predictor coefficient in all three required fits;
- finite strictly positive HC3 standard error in all three required fits;
- finite two-sided p-value in the pooled fit.

Any failed gate produces a deterministic failure status and makes the candidate unrankable.

No support threshold may be weakened after outcomes are inspected.

## Directional consistency

A candidate satisfies directional consistency only when the predictor coefficient has the same nonzero sign in:

- the pooled fit;
- partition-2 evaluation;
- partition-3 evaluation.

Zero, nonfinite, failed, or unavailable coefficients do not satisfy directional consistency.

## Multiplicity control

Benjamini-Hochberg false-discovery-rate correction at `q = 0.05` is applied separately within each outcome family:

- Family R: 24 tests;
- Family M: 24 tests;
- Family V: 24 tests.

Only rankable candidates enter the corresponding BH calculation.

Unrankable candidates retain null adjusted-q fields and remain visible.

A supported research association requires both:

- family-specific BH-adjusted q-value `<= 0.05`;
- directional consistency across pooled, partition-2, and partition-3 fits.

## Required canonical outputs

A future implementation handoff must define exact schemas and ordering for exactly ten canonical outputs under:

`artifacts/simple_btc_price_state_predictive_baselines/`

The planned outputs are:

1. `price_state_anchor_inventory.csv`;
2. `price_state_anchor_inventory.json`;
3. `price_state_candidate_inventory.csv`;
4. `price_state_candidate_inventory.json`;
5. `price_state_fold_plan.json`;
6. `price_state_results.csv`;
7. `price_state_results.json`;
8. `price_state_report.md`;
9. `price_state_source_manifest.json`;
10. `price_state_manifest.json`.

No output may contain current wall-clock timestamps, machine-specific absolute paths, random identifiers, unordered mappings, or nonfinite JSON values.

All canonical text must be UTF-8 and LF-only. JSON must be strict and deterministically serialized.

## Preflight requirement

Before any predictive outcome is generated, the future runner must support a governed preflight-only mode that verifies:

- source path and SHA-256;
- source byte count and row count;
- required schema;
- timestamp parsing, uniqueness, ordering, and exact hourly cadence;
- finite positive closes;
- deterministic anchor count and partition plan;
- exact predictor and candidate inventories;
- absence of output generation during preflight.

Preflight must report that predictive outcomes were not generated.

## Replay and immutability

A future governed implementation must:

1. record source bytes before generation;
2. complete one canonical generation;
3. copy or hash all canonical outputs;
4. complete a second canonical generation from the same governed source;
5. prove byte identity for all ten outputs;
6. rerun post-generation preflight;
7. prove governed source bytes are unchanged.

Any mismatch is a hard failure and prohibits publication.

## Required tests

A future implementation handoff must require focused tests covering at least:

- source identity and schema reconciliation;
- exact hourly timestamp enforcement;
- anchor origin and 168-hour spacing;
- partition assignment;
- all eight predictor formulas and interval boundaries;
- all three outcome formulas at all three horizons;
- missing-timestamp failures;
- development-only standardization;
- OLS coefficient construction;
- HC3 covariance;
- support gates;
- rank detection;
- directional consistency;
- family-specific BH correction;
- deterministic candidate ordering;
- strict JSON and LF-only output;
- two-run replay;
- source immutability;
- preflight producing no outcomes;
- fail-closed behavior.

## Stop conditions

Work must stop before outcome generation if any of the following occurs:

- source identity does not reconcile;
- the source is not an exact unique hourly sequence;
- a predictor, outcome, horizon, interval convention, estimator, support rule, or multiplicity rule is ambiguous;
- the candidate inventory is not exactly 72;
- deterministic ordering or serialization is unresolved;
- an implementation requires a file surface not separately authorized by the board;
- the specification or implementation handoff has not been frozen by commit;
- a separate implementation GO has not been recorded on the campaign board.

## Interpretation boundary

Campaign #48 may establish that one or more simple BTC price-state variables have a reproducible statistical association with future BTC return, return magnitude, or volatility under this exact design.

It may also establish a null, unstable, failed, or support-limited result.

It cannot by itself establish:

- deployable alpha;
- causal market structure;
- economic value;
- transaction-cost robustness;
- portfolio improvement;
- superiority to Core v1;
- production readiness.

Any supported candidate must enter a separately frozen confirmation campaign before any economic-value or Core v1 comparison.

## Current authorization boundary

At this draft stage, only specification review and amendment are authorized.

Not authorized yet:

- implementation code;
- runner code;
- tests;
- artifacts;
- outcome generation;
- result inspection;
- candidate ranking;
- implementation handoff;
- implementation GO;
- confirmation;
- economic testing;
- runtime integration.

## Freeze checklist

Before this document may be frozen, governance review must confirm:

- the source contract is exact;
- the eight predictors are simple, finite, and nonduplicative enough to justify separate testing;
- all interval endpoints are unambiguous;
- the three outcomes and three horizons are appropriate;
- the 168-hour anchor spacing is accepted;
- estimator and HC3 requirements are accepted;
- support and chronological-consistency gates are accepted;
- three independent 24-test BH families are accepted;
- the ten planned outputs are sufficient;
- no predictive outcome has been generated or inspected;
- no runtime or strategy surface has changed.
