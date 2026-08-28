# Campaign #48 — Simple BTC Price-State Predictive Baselines

## Status

**FROZEN GOVERNING SPECIFICATION — frozen before predictive outcome generation or inspection.**

No predictive outcomes may be generated, calculated, viewed, inspected, ranked, or interpreted until a separately frozen implementation handoff exists and the campaign board records a separate implementation GO.

Campaign #48 is research-only, observation-only, deterministic, replay-safe, chronological, leakage-safe, and fail-closed.

It authorizes no runtime, regime, threshold, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Plain-English question

Campaign #48 asks:

> Does BTC's recent price behavior contain reliable information about what happens next?

The purpose is to establish a transparent predictive baseline before Itera attributes value to regimes, transitions, machine learning, or more complicated signal logic.

This is not a trading-strategy backtest. It is a prespecified statistical discovery study over simple BTC price-state features.

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
- data rows: `70,069` excluding the header;
- first timestamp: `2018-01-01 00:00:00`;
- last timestamp: `2025-12-31 00:00:00`;
- cadence: exact hourly observations.

The exact ordered source schema is:

1. `timestamp`;
2. `open`;
3. `high`;
4. `low`;
5. `close`;
6. `volume`.

Only `timestamp` and `close` may enter Campaign #48 predictor or outcome calculations. The remaining fields are source-reconciliation fields only.

The implementation must fail closed if the path, digest, byte count, data-row count, ordered schema, ordering, timestamp uniqueness, first timestamp, last timestamp, or exact hourly cadence does not reconcile.

No source substitution, downloading, interpolation, filling, resampling, nearest-row matching, as-of matching, synthetic bars, or timestamp repair is permitted.

All close prices used by the campaign must be finite and strictly positive.

## Anchor construction

Campaign #48 uses one common deterministic 168-hour anchor grid so maximum-horizon outcomes do not overlap across adjacent anchors.

The anchor origin is the earliest governed source timestamp `t` for which every exact hourly close in `[t-168h, t]` exists.

Starting from that origin, scheduled anchors advance in exact 168-hour increments.

An anchor is retained in the anchor inventory when all eight frozen predictors can be computed. Outcome availability is recorded separately by family and horizon.

A missing scheduled anchor timestamp is not shifted or replaced. Because the governed source is required to be an exact unique hourly sequence, any cadence break is a preflight failure.

## Chronological partitions

The common anchor inventory is divided into three contiguous, near-equal chronological partitions.

If the anchor count is not divisible by three, remainder anchors are assigned to earlier partitions in chronological order.

Required evaluations are:

1. partition 1 is the development sample for partition-2 evaluation;
2. partitions 1 and 2 together are the development sample for partition-3 evaluation;
3. all candidate-complete anchors form the pooled fit.

No random split, shuffle, cross-sectional fold, bootstrap split, or future-informed preprocessing is permitted.

## Frozen predictor inventory

Campaign #48 contains exactly eight simple predictors.

Let `C_t` denote the close at exact timestamp `t`. Let hourly log return be:

`r_u = ln(C_u / C_{u-1h})`.

### 1. Trailing 24-hour log return

`return_trailing_24h = ln(C_t / C_{t-24h})`

### 2. Trailing 72-hour log return

`return_trailing_72h = ln(C_t / C_{t-72h})`

### 3. Trailing 168-hour log return

`return_trailing_168h = ln(C_t / C_{t-168h})`

### 4. Trailing 24-hour realized volatility

`realized_volatility_trailing_24h = sqrt(sum(r_u^2))`

using all 24 exact hourly returns with endpoint timestamps in `(t-24h, t]`.

No annualization is applied.

### 5. Trailing 168-hour realized volatility

`realized_volatility_trailing_168h = sqrt(sum(r_u^2))`

using all 168 exact hourly returns with endpoint timestamps in `(t-168h, t]`.

No annualization is applied.

### 6. Distance from trailing 168-hour close mean

Let `mean_168h` be the arithmetic mean of the 169 exact hourly closes in `[t-168h, t]`.

`distance_from_mean_trailing_168h = (C_t / mean_168h) - 1`

### 7. Position within trailing 168-hour range

Let `low_168h` and `high_168h` be the minimum and maximum of the 169 exact hourly closes in `[t-168h, t]`.

`range_position_trailing_168h = (C_t - low_168h) / (high_168h - low_168h)`

If `high_168h == low_168h`, this predictor is unavailable for the anchor. No substitute value is permitted.

### 8. Drawdown from trailing 168-hour high

`drawdown_from_high_trailing_168h = (C_t / high_168h) - 1`

## Predictor boundary

No additional indicators, thresholds, bins, labels, interactions, ratios, splines, polynomial terms, moving-average crossovers, oscillator names, technical-analysis pattern names, learned features, or data-dependent feature selection are authorized.

The three return windows are separate prespecified candidates. The two volatility windows are separate prespecified candidates. The three 168-hour price-location predictors are separate prespecified candidates despite expected correlation.

Expected correlation does not authorize dropping, combining, replacing, or reprioritizing a candidate after outcomes are generated or inspected.

## Frozen outcomes

Let horizon `h` be one of `24`, `72`, or `168` hours.

All outcomes require exact source timestamps. A missing endpoint or required hourly interval makes that outcome unavailable for the anchor.

### Family R — directional forward log return

`forward_return_h = ln(C_{t+h} / C_t)`

This is a continuous signed outcome. No separate binary up/down label is created.

### Family M — absolute forward return

`forward_absolute_return_h = abs(forward_return_h)`

### Family V — forward realized volatility

`forward_realized_volatility_h = sqrt(sum(r_u^2))`

using all `h` exact hourly returns with endpoint timestamps in `(t, t+h]`.

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
- exactly one standardized predictor;
- no regime labels;
- no regime fixed effects;
- no additional price controls;
- no interactions.

HC3 heteroskedasticity-consistent covariance is required.

Reported inferential quantities are:

- coefficient on the standardized predictor;
- HC3 standard error;
- two-sided normal p-value;
- 95% normal confidence interval using `1.959963984540054`.

No alternate estimator may be substituted after outcomes are generated or inspected.

## Development-only standardization

For partition-2 evaluation, predictor mean and population standard deviation are computed from candidate-complete partition-1 development rows only.

For partition-3 evaluation, predictor mean and population standard deviation are computed from candidate-complete development rows in partitions 1 and 2 only.

Population standard deviation is defined with divisor `n`, equivalent to `numpy.std(values, ddof=0)`.

The evaluation predictor is transformed using only the corresponding prior-development mean and population standard deviation.

For the pooled fit, pooled candidate-complete rows define the pooled mean and population standard deviation.

A candidate fit fails closed if its applicable development predictor mean or population standard deviation is nonfinite, or if the population standard deviation is not strictly positive.

Outcomes are not standardized.

## Fit interpretation

Campaign #48 is an association-discovery design.

For chronological evaluation fits, preprocessing parameters come only from prior development rows, while coefficient and HC3 inference are estimated on the applicable evaluation partition.

The campaign does not select hyperparameters, refit a production forecast, calculate trading positions, or convert coefficients into signals.

## Support and rankability gates

A candidate is rankable only when all of the following hold:

- at least 90 candidate-complete pooled anchors;
- at least 25 candidate-complete anchors in each chronological partition;
- finite predictor and outcome values in each required fit;
- finite development mean and strictly positive population standard deviation for each required transformation;
- full-column-rank design for pooled, partition-2, and partition-3 fits;
- finite nonzero predictor coefficient in all three required fits;
- finite strictly positive HC3 standard error in all three required fits;
- finite two-sided pooled p-value.

Any failed gate produces a deterministic failure status and makes the candidate unrankable.

No support threshold may be weakened after outcomes are generated or inspected.

## Directional consistency

A candidate satisfies directional consistency only when the predictor coefficient has the same nonzero sign in:

- the pooled fit;
- partition-2 evaluation;
- partition-3 evaluation.

Zero, nonfinite, failed, or unavailable coefficients do not satisfy directional consistency.

## Multiplicity control

Benjamini-Hochberg false-discovery-rate correction at `q = 0.05` is applied separately within each outcome family:

- Family R: 24 prespecified tests;
- Family M: 24 prespecified tests;
- Family V: 24 prespecified tests.

Only rankable candidates enter the corresponding BH calculation. Ties must be handled deterministically using candidate identifier as the secondary ordering key.

Unrankable candidates retain null adjusted-q fields and remain visible.

A supported research association requires both:

- family-specific BH-adjusted q-value `<= 0.05`;
- directional consistency across pooled, partition-2, and partition-3 fits.

## Required canonical outputs

A future implementation handoff must define exact schemas and deterministic ordering for exactly ten canonical outputs under:

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

- source path, SHA-256, byte count, and data-row count;
- exact ordered six-column schema;
- timestamp parsing, uniqueness, ordering, first timestamp, last timestamp, and exact hourly cadence;
- finite strictly positive closes;
- deterministic anchor count and partition plan;
- exact predictor and candidate inventories;
- absence of output generation during preflight.

Preflight must explicitly report that predictive outcomes were not generated.

## Replay and immutability

A future governed implementation must:

1. record governed source bytes before generation;
2. complete one canonical generation;
3. copy or hash all canonical outputs;
4. complete a second canonical generation from the same governed source;
5. prove byte identity for all ten outputs;
6. rerun post-generation preflight;
7. prove governed source bytes are unchanged.

Any mismatch is a hard failure and prohibits publication.

## Required tests

A future implementation handoff must require focused tests covering at least:

- source identity and exact ordered schema reconciliation;
- exact hourly timestamp enforcement;
- anchor origin and 168-hour spacing;
- partition assignment;
- all eight predictor formulas and interval boundaries;
- all three outcome formulas at all three horizons;
- missing-timestamp failures;
- development-only population standardization with `ddof=0`;
- OLS coefficient construction;
- HC3 covariance;
- support gates;
- rank detection;
- directional consistency;
- deterministic family-specific BH correction;
- deterministic candidate ordering;
- strict JSON and LF-only output;
- two-run replay;
- source immutability;
- preflight producing no outcomes;
- fail-closed behavior.

## Stop conditions

Work must stop before outcome generation if any of the following occurs:

- source identity or exact schema does not reconcile;
- the source is not an exact unique hourly sequence;
- a predictor, outcome, horizon, interval convention, estimator, transformation, support rule, or multiplicity rule is ambiguous;
- the candidate inventory is not exactly 72;
- deterministic ordering or serialization is unresolved;
- an implementation requires a file surface not separately authorized by the board;
- this specification or the implementation handoff has not been frozen by commit;
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

This specification is frozen, but implementation remains prohibited.

Not authorized yet:

- implementation code;
- runner code;
- tests;
- artifacts;
- outcome generation;
- result inspection;
- candidate ranking;
- implementation handoff unless separately authorized by the campaign board;
- implementation GO;
- confirmation;
- economic testing;
- runtime integration.

## Freeze record

This specification was frozen before any Campaign #48 predictive outcome was generated, calculated, viewed, inspected, ranked, or interpreted.

The freeze commit is the commit that first records this document with status `FROZEN GOVERNING SPECIFICATION`.
