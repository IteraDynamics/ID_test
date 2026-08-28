# Campaign #47 — Historical Regime Persistence, Duration, Clustering, and Spacing Discovery

## Status

Frozen research specification. Governance and design only. Predictive implementation, outcome generation, estimator execution, result inspection, candidate ranking, strategy testing, and runtime integration remain unauthorized until a separate implementation GO is recorded on `docs/ITERA_CAMPAIGN_BOARD.md`.

## Purpose

Campaign #47 tests whether the temporal structure of BTC regime states contains reproducible information beyond exact ordered transition identity and beyond simple recent BTC price state.

Campaign #45 found no supported exact ordered-transition association and showed that 42 of 51 transition-by-horizon candidates lacked sufficient binary-side support. Campaign #47 therefore shifts from sparse exact transition categories to broadly supported continuous structural features derived from the canonical Campaign #46 hourly regime-state ledger.

The campaign is research-only, observation-only, deterministic, replay-safe, leakage-safe, and fail-closed. It does not authorize any change to runtime behavior, regime labels, thresholds, signals, orders, execution, portfolio construction, NAV, exposure, dashboards, or model training.

## Research questions

1. Does current regime age contain incremental forward-return, move-magnitude, volatility, or regime-survival information?
2. Does the duration of the immediately preceding completed regime contain incremental information?
3. Does time since the most recent transition contain incremental information?
4. Does recent transition density over 24, 72, or 168 hours contain incremental information?
5. Are any supported effects directionally stable across chronological evaluation partitions?

## Governed source contract

### Canonical regime source

Use only the canonical Campaign #46 publication under:

`artifacts/full_historical_regime_state_sequence/`

Required source files:

- `btc_hourly_regime_state_manifest.json`;
- `btc_hourly_regime_state_sequence.csv`;
- `btc_hourly_regime_state_runs.csv`;
- `btc_hourly_regime_transitions.csv`.

Campaign #46 publication commit: `34a6999`.

The implementation must fail closed if any source identity, digest, schema, count, ordering, timestamp, label, run, or transition relationship differs from the canonical manifest.

### Underlying BTC source

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- byte count: `4,792,028`;
- rows: `70,069`;
- first timestamp: `2018-01-01 00:00:00`;
- last timestamp: `2025-12-31 00:00:00`;
- exact timestamp matching only.

No interpolation, filling, resampling, nearest-row matching, as-of matching, synthetic bars, or source substitution is permitted.

## Anchor construction

### Eligibility

An anchor is eligible only when:

- its Campaign #46 regime label is non-`UNKNOWN`;
- all six frozen trailing BTC controls are available at the anchor;
- the structural predictor being tested is available;
- the exact forward endpoint required by the outcome exists;
- no source or schema reconciliation failure is present.

### Independence rule

Use a single deterministic 168-hour anchor grid for all candidate families and all horizons:

1. begin at the earliest eligible canonical hourly row for which all 168-hour trailing controls are available;
2. select that row as the first grid anchor;
3. select subsequent anchors at exact 168-hour timestamp increments;
4. omit a scheduled grid timestamp when the exact timestamp is absent or ineligible;
5. never replace an omitted timestamp with a nearby row.

This common grid prevents outcome overlap at the maximum 168-hour horizon and preserves one frozen anchor inventory across all tests.

### Chronological partitions

Partition the frozen anchor inventory into three contiguous chronological partitions using deterministic near-equal counts:

- partition 1: initial development;
- partition 2: first evaluation;
- partition 3: second evaluation.

When counts do not divide exactly, earlier partitions receive the extra rows in ordinal order. Partition membership must be serialized before any outcome ranking or inspection.

## Frozen structural predictors

Each predictor is evaluated separately. No interactions, thresholds, bins, splines, polynomial terms, or data-dependent feature selection are authorized.

1. `log1p_current_state_age_hours`
   - hours elapsed since the current canonical regime run began at the anchor, inclusive convention frozen as `anchor_timestamp - run_start_timestamp` in hours;
   - transformed as `log1p(hours)`.

2. `log1p_previous_state_duration_hours`
   - completed duration in hours of the immediately preceding canonical regime run;
   - unavailable when no prior completed run exists;
   - transformed as `log1p(hours)`.

3. `log1p_hours_since_previous_transition`
   - hours from the most recent canonical transition anchor to the current anchor;
   - transformed as `log1p(hours)`.

4. `transition_count_trailing_24h`
   - number of canonical transition anchors in `(anchor - 24 hours, anchor]`.

5. `transition_count_trailing_72h`
   - number of canonical transition anchors in `(anchor - 72 hours, anchor]`.

6. `transition_count_trailing_168h`
   - number of canonical transition anchors in `(anchor - 168 hours, anchor]`.

The transition at the anchor, when present, is included by the right-closed interval convention. Self-transitions and `UNKNOWN`-involving transitions remain exactly as represented by the canonical source ledger; the implementation may not silently relabel or remove them when calculating transition density.

## Frozen outcomes

All outcomes use exact timestamps and horizons of 24, 72, and 168 hours.

### Family R — directional forward return

`forward_log_return_{h}h = log(close[t+h] / close[t])`

### Family M — forward move magnitude

`absolute_forward_log_return_{h}h = abs(log(close[t+h] / close[t]))`

### Family V — forward realized volatility

Square root of the sum of squared exact hourly log returns over `(t, t+h]`.

If any required hourly timestamp inside the interval is absent, the outcome is unavailable. No gap filling is permitted.

### Family S — current-regime survival

Binary indicator equal to `1` only when the canonical regime label at exact timestamp `t+h` equals the anchor's canonical regime label and no intervening different canonical regime label occurs over `(t, t+h]`; otherwise `0`.

If any exact hourly timestamp required to determine uninterrupted survival is absent, the outcome is unavailable.

## Frozen controls

Each estimator includes:

1. trailing 24-hour log return;
2. trailing 72-hour log return;
3. trailing 168-hour log return;
4. trailing 24-hour realized volatility;
5. trailing 168-hour realized volatility;
6. normalized distance from trailing 168-hour close mean;
7. current-regime fixed effects using the canonical non-`UNKNOWN` labels present in the development sample.

Continuous predictors and continuous controls are standardized using development rows only for each chronological evaluation. The reference regime label is the lexicographically first development-present non-`UNKNOWN` label. Evaluation rows containing a regime label absent from development fail closed for that estimator sample rather than creating a new level.

For the pooled descriptive confirmatory fit, scaling and fixed-effect levels are derived from the complete pooled eligible sample and are explicitly distinguished from chronological evaluation fits.

## Estimator

For every predictor-outcome-horizon candidate:

- ordinary least squares with intercept;
- one standardized structural predictor;
- six standardized continuous BTC controls;
- current-regime fixed effects;
- HC3 heteroskedasticity-consistent covariance;
- two-sided normal-approximation p-value;
- 95% normal-approximation confidence interval.

Family S uses the same OLS-HC3 specification as a linear probability model. Its coefficient is interpreted only as a probability-point association per one development-standard-deviation increase in the predictor. No probability calibration claim is authorized.

## Candidate family and multiplicity

The frozen candidate inventory contains:

- 6 structural predictors;
- 4 outcome families;
- 3 horizons;
- 72 total predictor-outcome-horizon candidates.

Benjamini-Hochberg false-discovery-rate correction at `q = 0.05` is applied separately within each of the four prespecified outcome families:

- Family R: 18 tests;
- Family M: 18 tests;
- Family V: 18 tests;
- Family S: 18 tests.

Unrankable candidates remain visible and do not enter BH ranking. The exact rankable family membership must be serialized before adjusted values are calculated.

## Minimum support and rankability

A candidate is rankable only when all of the following hold:

- at least 90 complete pooled anchors;
- at least 25 complete anchors in each chronological partition;
- predictor finite and nonconstant in each development and evaluation estimator sample;
- all required design matrices have full column rank;
- HC3 standard error is finite and strictly positive;
- pooled and evaluation coefficients are finite and nonzero;
- no development-absent regime level appears in the applicable evaluation sample;
- no governed reconciliation or outcome-availability rule is violated.

Failure reasons must remain explicit and serialized. Missing, null, failed, and insufficient-support candidates may not be dropped from canonical outputs.

## Directional consistency

A rankable candidate is directionally consistent only when:

- the partition-2 evaluation coefficient;
- the partition-3 evaluation coefficient; and
- the pooled coefficient

are all finite, nonzero, and share the same sign.

A candidate is a supported research association only when:

- its BH-adjusted q-value within its prespecified outcome family is `<= 0.05`; and
- directional consistency is true.

A supported association is not a strategy, alpha, deployability, sizing, timing, or economic-value claim.

## Canonical outputs

The eventual implementation, if separately authorized, must publish exactly:

1. `regime_structure_source_manifest.json`;
2. `regime_structure_anchor_inventory.json`;
3. `regime_structure_anchor_inventory.csv`;
4. `regime_structure_candidate_inventory.json`;
5. `regime_structure_candidate_inventory.csv`;
6. `regime_structure_fold_plan.json`;
7. `regime_structure_results.json`;
8. `regime_structure_results.csv`;
9. `regime_structure_report.md`;
10. `regime_structure_manifest.json`.

Canonical text must be UTF-8, LF-only, deterministically ordered, strict JSON where applicable, and byte-identical across two governed runs.

## Acceptance gates

Before any result may be treated as governed evidence:

1. this specification predates predictive outcome generation;
2. the implementation handoff predates predictive outcome generation;
3. the board records a separate implementation GO;
4. all governed source identities and relationships pass preflight;
5. the anchor, predictor, candidate, outcome, and partition inventories reconcile exactly;
6. focused tests pass;
7. controls, transformations, scaling, fixed effects, outcomes, OLS, HC3, support gates, directional rules, and BH correction reconcile exactly;
8. null, missing, failed, and insufficient-support candidates remain visible;
9. two governed runs produce byte-identical outputs;
10. all canonical text is LF-only and all JSON is strict;
11. governed source bytes remain identical before and after generation;
12. the full repository suite passes with no new failures;
13. scope review finds no runtime, threshold, regime, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes;
14. any supported result remains research-only and requires a separate confirmation campaign before any Core v1 overlay or economic-value test.

## Explicitly unauthorized

- implementation before a separate board GO;
- predictive outcome generation or inspection;
- candidate ranking or selective redefinition after seeing results;
- changes to `BaselineRegimeEngine` or canonical Campaign #46 labels;
- thresholds, bins, interactions, transformations, outcomes, controls, horizons, estimators, or multiplicity methods not frozen here;
- Core v1 overlay testing;
- Sharpe, CAGR, drawdown, turnover, allocation, sizing, or economic optimization;
- production or paper-runtime integration;
- signals, orders, execution, portfolio, NAV, exposure, or dashboard changes;
- model training, replacement, or recalibration.

## Research progression

If Campaign #47 produces one or more supported research associations, the next required stage is a separately governed confirmation campaign using only frozen candidates. Only candidates that survive confirmation may enter a later, separately authorized incremental-value comparison against untouched Core v1.