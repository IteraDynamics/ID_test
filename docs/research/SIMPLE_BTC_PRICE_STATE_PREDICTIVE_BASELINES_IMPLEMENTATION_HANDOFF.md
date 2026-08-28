# Campaign #48 — Simple BTC Price-State Predictive Baselines Implementation Handoff

## Status

**FROZEN IMPLEMENTATION HANDOFF — frozen before implementation, predictive outcome generation, or result inspection.**

This handoff implements specification freeze `e8777df3442d093fd84fb92c25d13aadc2bfe1ed` without amendment.

It does not itself authorize implementation. A separate board-recorded implementation GO is required before any implementation file, test, artifact, estimator run, predictive outcome, or result may be created or inspected.

Campaign #48 remains deterministic, replay-safe, chronological, leakage-safe, observation-only, research-only, and fail-closed.

## Governing documents

- authoritative board: `docs/ITERA_CAMPAIGN_BOARD.md`;
- frozen specification: `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES.md`;
- specification freeze: `e8777df3442d093fd84fb92c25d13aadc2bfe1ed`;
- this handoff: `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES_IMPLEMENTATION_HANDOFF.md`.

Any disagreement between implementation and the frozen specification is a stop condition. This handoff may clarify implementation detail but may not alter predictor definitions, windows, outcomes, horizons, estimator, support gates, chronological rules, multiplicity rules, or interpretation boundaries.

## Proposed implementation branch

After a separate implementation GO, implementation should occur on:

`agent/campaign-48-simple-btc-price-state-baselines-implementation`

The branch must start from the governance commit that records the implementation GO.

## Exact implementation file surfaces

A future implementation GO may authorize only these implementation paths:

1. `research/ml/validation/simple_btc_price_state_predictive_baselines.py`;
2. `scripts/run_simple_btc_price_state_predictive_baselines.py`;
3. `tests/test_simple_btc_price_state_predictive_baselines.py`;
4. `artifacts/simple_btc_price_state_predictive_baselines/**` only during governed artifact publication;
5. `docs/ITERA_CAMPAIGN_BOARD.md` only for later implementation authorization and closure transitions.

No runtime, strategy, signal, order, execution, portfolio, NAV, exposure, dashboard, threshold, regime, classifier, or model-training file is authorized.

## Frozen source contract

The module must expose a frozen source contract equivalent to:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- byte count: `4_792_028`;
- data-row count: `70_069`;
- first timestamp: `2018-01-01 00:00:00`;
- last timestamp: `2025-12-31 00:00:00`;
- exact ordered columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`;
- cadence: exactly one unique row per hour.

Only `timestamp` and `close` may enter predictor or outcome calculations.

Source verification must occur before any outcome calculation. Any mismatch must terminate the run with no canonical output publication.

## Frozen constants

The implementation must define immutable ordered constants equivalent to:

### Predictors

1. `return_trailing_24h`;
2. `return_trailing_72h`;
3. `return_trailing_168h`;
4. `realized_volatility_trailing_24h`;
5. `realized_volatility_trailing_168h`;
6. `distance_from_mean_trailing_168h`;
7. `range_position_trailing_168h`;
8. `drawdown_from_high_trailing_168h`.

### Outcome families

1. `R` — directional forward log return;
2. `M` — absolute forward log return;
3. `V` — forward realized volatility.

### Horizons

`24`, `72`, `168` hours.

### Candidate ordering

Candidates must be ordered by:

1. predictor order above;
2. outcome-family order `R`, `M`, `V`;
3. horizon order `24`, `72`, `168`.

Candidate identifiers must be:

`{predictor}__{family}__{horizon}h`

The resulting inventory must contain exactly 72 candidates.

## Required public module interface

The analysis module should expose side-effect-free functions or equivalent interfaces for:

- source hashing and strict source loading;
- source-contract reconciliation;
- anchor construction;
- chronological partition counts and assignment;
- predictor construction;
- candidate inventory construction;
- exact-horizon outcome construction;
- candidate-complete sample construction;
- development-only population standardization;
- OLS-HC3 estimation;
- rankability evaluation;
- directional-consistency evaluation;
- family-specific Benjamini-Hochberg correction;
- deterministic result assembly;
- strict JSON and LF-only CSV/Markdown serialization;
- canonical manifest construction;
- preflight reporting.

Importing the module must not read files, create directories, write artifacts, inspect outcomes, or mutate repository state.

## Anchor schema and ordering

`price_state_anchor_inventory.csv` and its JSON counterpart must contain one row per retained anchor ordered by `anchor_ordinal` ascending.

Required fields, in exact CSV order:

1. `anchor_ordinal`;
2. `anchor_timestamp`;
3. `partition`;
4. `return_trailing_24h`;
5. `return_trailing_72h`;
6. `return_trailing_168h`;
7. `realized_volatility_trailing_24h`;
8. `realized_volatility_trailing_168h`;
9. `distance_from_mean_trailing_168h`;
10. `range_position_trailing_168h`;
11. `drawdown_from_high_trailing_168h`.

The JSON representation must preserve this semantic field set and anchor ordering.

No forward outcome may appear in the anchor inventory.

## Candidate schema and ordering

`price_state_candidate_inventory.csv` and its JSON counterpart must contain exactly 72 rows in frozen candidate order.

Required fields, in exact CSV order:

1. `candidate_ordinal`;
2. `candidate_id`;
3. `predictor`;
4. `outcome_family`;
5. `horizon_hours`;
6. `outcome_column`.

`candidate_ordinal` is zero-based and contiguous.

## Fold-plan schema

`price_state_fold_plan.json` must include:

- anchor count;
- partition counts;
- partition start and end ordinals;
- partition start and end timestamps;
- partition-2 development partitions `[1]` and evaluation partition `2`;
- partition-3 development partitions `[1, 2]` and evaluation partition `3`;
- pooled partitions `[1, 2, 3]`;
- anchor spacing hours `168`;
- remainder-assignment rule `earlier_partitions_first`.

The fold plan must contain no predictive outcomes or statistical results.

## Outcome construction boundary

Outcomes may be constructed only after governed preflight passes and only during a non-preflight governed generation run.

For each anchor and horizon, exact timestamps are mandatory. No interpolation, filling, resampling, nearest-row matching, as-of matching, timestamp shifting, or synthetic bars are permitted.

Outcome columns are:

- `outcome_R_24h`, `outcome_R_72h`, `outcome_R_168h`;
- `outcome_M_24h`, `outcome_M_72h`, `outcome_M_168h`;
- `outcome_V_24h`, `outcome_V_72h`, `outcome_V_168h`.

Unavailable outcomes remain unavailable and must not be imputed.

## Standardization contract

For each candidate fit:

- partition-2 evaluation uses mean and population standard deviation from candidate-complete partition-1 rows;
- partition-3 evaluation uses mean and population standard deviation from candidate-complete partition-1 and partition-2 rows;
- pooled fit uses mean and population standard deviation from all pooled candidate-complete rows;
- population standard deviation is `numpy.std(values, ddof=0)`;
- outcomes are never standardized.

The exact mean and population standard deviation used for each required fit must be serialized in result records when the fit reaches standardization. Failed or unavailable fits retain null fields.

## OLS-HC3 contract

Each fit uses a two-column design:

1. intercept;
2. standardized predictor.

Required estimator behavior:

- require full column rank;
- solve ordinary least squares deterministically;
- compute HC3 covariance using leverage adjustment `(1 - h_ii)^{-2}`;
- fail closed if any leverage denominator is not strictly positive;
- require finite coefficient;
- require finite strictly positive predictor variance and standard error;
- compute two-sided normal p-value;
- compute 95% normal confidence interval using `1.959963984540054`.

No alternate estimator, covariance, optimizer, regularizer, fallback inverse, pseudoinverse, or tolerance-based silent repair is permitted.

## Deterministic statuses

Every candidate must receive exactly one final status from this ordered vocabulary:

1. `SUPPORTED_RESEARCH_ASSOCIATION`;
2. `MULTIPLICITY_NOT_MET`;
3. `DIRECTION_INCONSISTENT`;
4. `INSUFFICIENT_SUPPORT`;
5. `OUTCOME_OR_PREDICTOR_UNAVAILABLE`;
6. `ZERO_OR_NONFINITE_VARIANCE`;
7. `RANK_DEFICIENT_DESIGN`;
8. `ESTIMATOR_FAILURE`.

Status precedence for unrankable candidates is the first applicable failure in this order:

1. outcome or predictor unavailable;
2. insufficient support;
3. zero or nonfinite development variance;
4. rank-deficient design;
5. estimator failure.

For rankable candidates:

1. if BH-adjusted q-value exceeds `0.05`, status is `MULTIPLICITY_NOT_MET`;
2. otherwise, if directional consistency fails, status is `DIRECTION_INCONSISTENT`;
3. otherwise status is `SUPPORTED_RESEARCH_ASSOCIATION`.

No candidate may disappear because of failure.

## Results schema and ordering

`price_state_results.csv` and its JSON counterpart must contain exactly 72 rows in candidate order.

Required fields, in exact CSV order:

1. `candidate_ordinal`;
2. `candidate_id`;
3. `predictor`;
4. `outcome_family`;
5. `horizon_hours`;
6. `status`;
7. `rankable`;
8. `directionally_consistent`;
9. `pooled_n_obs`;
10. `partition_1_complete_n`;
11. `partition_2_complete_n`;
12. `partition_3_complete_n`;
13. `pooled_development_mean`;
14. `pooled_development_population_std`;
15. `pooled_coefficient`;
16. `pooled_standard_error_hc3`;
17. `pooled_p_value`;
18. `pooled_confidence_interval_low`;
19. `pooled_confidence_interval_high`;
20. `partition_2_development_mean`;
21. `partition_2_development_population_std`;
22. `partition_2_coefficient`;
23. `partition_2_standard_error_hc3`;
24. `partition_2_p_value`;
25. `partition_2_confidence_interval_low`;
26. `partition_2_confidence_interval_high`;
27. `partition_3_development_mean`;
28. `partition_3_development_population_std`;
29. `partition_3_coefficient`;
30. `partition_3_standard_error_hc3`;
31. `partition_3_p_value`;
32. `partition_3_confidence_interval_low`;
33. `partition_3_confidence_interval_high`;
34. `family_bh_rank`;
35. `family_bh_adjusted_q_value`;
36. `failure_reason`.

Boolean CSV values must serialize as lowercase `true` or `false`. Null CSV values are empty fields. Strict JSON null is used for unavailable values.

## Benjamini-Hochberg contract

BH is applied separately to rankable candidates within each frozen outcome family.

Within a family:

1. sort by pooled p-value ascending;
2. break p-value ties by candidate identifier ascending;
3. assign one-based BH ranks;
4. compute raw adjusted value `p * m / rank`;
5. apply reverse cumulative minimum;
6. cap adjusted q-values at `1.0`;
7. map values back to frozen candidate order.

Unrankable candidates retain null BH rank and adjusted q-value.

## Report contract

`price_state_report.md` must be generated only from canonical structured payloads and must include:

- source identity summary;
- anchor and partition counts;
- frozen predictor, outcome, horizon, and candidate counts;
- rankable and unrankable counts;
- status counts in frozen status order;
- supported-candidate table in candidate order;
- explicit interpretation boundary;
- explicit statement that no runtime or strategy authorization follows.

The report must not introduce analysis, filtering, ranking, claims, or recommendations absent from canonical structured results.

## Source-manifest contract

`price_state_source_manifest.json` must include:

- repository-relative source path;
- SHA-256;
- byte count;
- data-row count;
- exact ordered schema;
- first and last timestamps;
- cadence hours;
- source reconciliation status;
- explicit `predictive_outcomes_generated` boolean.

Preflight output must set `predictive_outcomes_generated` to `false`.

## Canonical manifest contract

`price_state_manifest.json` must include:

- campaign identifier `48`;
- specification freeze commit;
- implementation-handoff freeze commit supplied by the runner contract;
- source-manifest digest;
- frozen predictor, outcome-family, horizon, and candidate inventories;
- anchor and partition counts;
- ordered list of all ten canonical files;
- byte count and SHA-256 for each other canonical file;
- deterministic payload digest over the normalized structured campaign payload;
- serialization contract version;
- explicit `research_only`, `observation_only`, and `predictive_outcomes_generated` fields.

The manifest must not hash itself. Its own digest is established by Git or external verification.

## Serialization contract

Canonical JSON:

- UTF-8;
- LF-only;
- sorted mapping keys;
- two-space indentation;
- terminal newline;
- strict JSON with `allow_nan=False`;
- nonfinite numeric values normalized to null;
- negative zero normalized to `0.0`.

Canonical CSV:

- UTF-8;
- LF-only;
- exact frozen column order;
- terminal newline;
- deterministic float formatting equivalent to `.17g`;
- lowercase booleans;
- empty field for null;
- no extra columns.

Canonical Markdown:

- UTF-8;
- LF-only;
- terminal newline;
- generated deterministically from structured canonical payloads.

No canonical output may contain current wall-clock time, random identifiers, absolute machine paths, environment-specific temporary paths, unordered collections, or platform-dependent newline behavior.

## Runner contract

The future runner must provide:

- `--preflight-only` mode;
- governed generation mode;
- explicit source path argument defaulting to the frozen source;
- explicit output directory argument defaulting to the canonical artifact directory;
- staged output construction in a temporary sibling directory;
- atomic publication only after every file validates;
- refusal to overwrite a nonempty canonical directory unless an explicit governed replacement flag is supplied;
- machine-readable terminal summary;
- nonzero exit on any failure.

`--preflight-only` must:

- verify the complete source contract;
- construct predictor, candidate, anchor, and partition inventories;
- generate no forward outcomes;
- run no estimator;
- write no canonical result artifacts;
- explicitly report `predictive_outcomes_generated: false`.

Governed generation must:

1. run preflight internally;
2. record source digest before outcome construction;
3. construct outcomes and results;
4. build all ten outputs in staging;
5. validate strict JSON, LF-only text, schemas, counts, ordering, and manifest reconciliation;
6. verify source digest unchanged;
7. publish atomically.

## Replay contract

Governed acceptance requires two complete generation runs from identical source bytes and identical frozen code.

All ten canonical files must be byte-identical across runs.

After the second run:

- rerun preflight;
- verify `predictive_outcomes_generated: false` in preflight;
- verify source bytes unchanged;
- verify every canonical file is UTF-8 and LF-only;
- verify both result representations contain exactly 72 candidates in identical order.

Any mismatch prohibits publication.

## Required focused tests

The focused test file must cover at least:

1. exact source identity and six-column ordering;
2. timestamp parsing, uniqueness, ordering, endpoints, and hourly cadence;
3. finite strictly positive close enforcement;
4. anchor origin and exact 168-hour spacing;
5. remainder assignment to earlier chronological partitions;
6. each of the eight predictor formulas and interval endpoints;
7. each of the nine outcome columns and exact endpoints;
8. missing timestamp and unavailable-outcome behavior;
9. exact 72-candidate inventory and ordering;
10. candidate-complete support counts;
11. development-only mean and `ddof=0` standardization;
12. zero and nonfinite variance failures;
13. two-column OLS coefficient calculation;
14. HC3 covariance and leverage-denominator failure;
15. full-rank detection;
16. deterministic status precedence;
17. directional consistency;
18. BH tie-breaking, reverse cumulative minimum, and family isolation;
19. null visibility for failed candidates;
20. strict JSON normalization and rejection of nonfinite constants;
21. exact CSV columns, booleans, floats, nulls, and LF output;
22. deterministic report generation;
23. canonical manifest reconciliation;
24. preflight producing no outcomes, estimator calls, or canonical files;
25. two-run byte replay;
26. source immutability;
27. atomic publication and failure cleanup;
28. import-time absence of side effects.

Synthetic tests must not inspect or tune against governed predictive results.

## Governed execution sequence after implementation GO

1. create the implementation branch from the board-recorded GO commit;
2. implement only the three authorized implementation files;
3. run focused tests using synthetic fixtures;
4. run governed preflight only;
5. inspect preflight evidence and confirm no predictive outcomes were generated;
6. only then run canonical generation;
7. run canonical generation a second time;
8. verify byte identity across all ten outputs;
9. rerun post-generation preflight;
10. verify governed source bytes unchanged;
11. inspect canonical results without changing the frozen design;
12. run the full repository suite;
13. review exact branch scope;
14. publish only the ten authorized artifacts;
15. close Campaign #48 in a separate board transition only if every acceptance gate passes.

## Stop conditions

Stop immediately and do not generate or inspect outcomes if:

- the board does not record a separate implementation GO;
- the implementation branch does not descend from that GO;
- the specification or handoff differs from its frozen commit;
- source identity or schema does not reconcile;
- any predictor, outcome, interval, estimator, support, status, ordering, or serialization rule is ambiguous;
- candidate inventory is not exactly 72;
- implementation requires an unauthorized path;
- focused tests fail;
- preflight generates outcomes, invokes the estimator, or writes result artifacts;
- source bytes change;
- canonical files do not reconcile or replay byte-identically;
- runtime, threshold, regime, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training surfaces change.

## Interpretation boundary

Implementation of this handoff may produce only a governed research result under the frozen design.

A supported association does not establish deployable alpha, economic value, transaction-cost robustness, portfolio improvement, superiority to Core v1, or production readiness.

Any supported candidate must enter a separately frozen confirmation campaign before any economic-value or Core v1 comparison.
