# Campaign #45 — Historical Regime State and Transition Discovery

## Status

Specification superseded and frozen for implementation on `agent/campaign-45-historical-regime-transitions` after Campaign #46 established a governed full-history transition source.

Campaign #45 is research-only, observation-only, deterministic, replay-safe, leakage-safe, anchor-local, and fail-closed. It does not authorize production, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes.

## Immediate objective

Test whether pre-registered BTC ordered regime transitions contain reproducible incremental forward-return information beyond simple anchor-local BTC price-state controls.

Source feasibility is established. Predictive value is not.

## Exact research question

Across the canonical Campaign #46 BTC hourly regime-transition ledger, do pre-registered ordered non-`UNKNOWN` transitions show directionally stable out-of-sample association with forward BTC log returns after adjustment for frozen simple BTC price-state controls and multiplicity?

## Governing source contract

Campaign #45 must use the canonical Campaign #46 publication at:

`artifacts/full_historical_regime_state_sequence/`

Required files:

- `btc_hourly_regime_transitions.csv`;
- `btc_hourly_regime_support_feasibility.json`;
- `btc_hourly_regime_state_manifest.json`.

Publication commit: `34a6999`.

Underlying BTC source:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- rows: `70,069`;
- exact timestamps only;
- no interpolation, filling, resampling, nearest-row matching, or as-of matching.

Any identity, hash, schema, count, ordering, timestamp, or manifest disagreement fails closed before outcome generation.

## Unit of observation and independence

The primary observation unit is one Campaign #46 transition anchor retained by the frozen 168-hour chronological purge.

Frozen source evidence:

- total transitions: `2,789`;
- eligible non-`UNKNOWN` transitions: `2,788`;
- independent purged transitions: `242`;
- chronological evidence partitions: `81`, `81`, `80`.

Only the 242 purged observations may enter modeling, descriptive candidate statistics, support counts, fold evidence, significance calculations, or rankings. Purged-out transitions remain visible in source reconciliation but may not be treated as independent evidence.

## Frozen predictor inventory

### Confirmatory predictor class

`P-003` ordered state transition:

`<prior_regime> -> <current_regime>`

Rules:

- both labels must be non-`UNKNOWN`;
- self-transitions are excluded;
- labels are taken exactly from the canonical Campaign #46 transition ledger;
- no merged, learned, clustered, embedded, thresholded, or post-result transition classes are allowed;
- deterministic candidate IDs are assigned before outcomes are inspected.

### Descriptive-only fields

Current state, prior state, state age, run duration, and transition spacing may be serialized when already present and anchor-local, but they are not confirmatory candidate classes in Campaign #45.

## Frozen BTC price-state controls

The exact control vector is:

1. trailing 24-hour log return;
2. trailing 72-hour log return;
3. trailing 168-hour log return;
4. trailing 24-hour realized volatility from hourly log returns;
5. trailing 168-hour realized volatility from hourly log returns;
6. distance from the trailing 168-hour close mean divided by trailing 168-hour close standard deviation when finite and positive.

All windows end at the anchor timestamp. Exact required timestamps must exist. Missing or non-finite controls make the affected observation ineligible for the controlled estimator and remain visible with an exclusion reason.

Controls are standardized using development-partition means and population standard deviations only. Those statistics are applied unchanged to the subsequent evaluation partition. A zero or non-finite development standard deviation fails the affected fit closed.

No control bins, thresholds, transformations, substitutions, or selections may be tuned after outcome inspection.

## Frozen outcome and horizons

Primary outcome:

- forward BTC log return from exact anchor close to exact horizon close.

Frozen horizons:

- 24 hours;
- 72 hours;
- 168 hours.

Maximum adverse excursion, strategy returns, Sharpe ratios, transaction costs, turnover, drawdown, positions, orders, NAV, and exposure are outside Campaign #45.

## Candidate inventory

The complete confirmatory family is the Cartesian product of:

- every distinct eligible ordered transition category present in the 242-observation purged source;
- horizons `24`, `72`, and `168` hours.

The inventory must be serialized before result ranking. Every candidate remains visible, including null, missing, failed, and insufficient-support candidates. No candidate may be added, merged, transformed, or dropped after outcomes are inspected.

## Minimum support gates

A candidate is rankable only when all are true:

- at least 20 independent observations overall;
- at least 5 independent observations in each of the three chronological evidence partitions;
- at least 5 candidate-present and at least 5 candidate-absent observations in each required estimator sample;
- exact anchor, controls, and horizon closes are available;
- no duplicate anchor exists;
- no leakage or timestamp ambiguity exists.

These gates control interpretability only and do not imply deployability or economic significance.

## Chronological evaluation

The three Campaign #46 partitions remain frozen as chronological evidence partitions with counts `81`, `81`, and `80`.

Expanding evaluation is defined as:

- partition 1: initial development block;
- partition 2: evaluated using scaling and encoding fit only on partition 1;
- partition 3: evaluated using scaling and encoding fit only on partitions 1 and 2.

This pre-result amendment supersedes the prior requirement for three separate evaluation folds. Campaign #45 therefore requires two genuine expanding out-of-sample evaluations while preserving minimum candidate support in all three evidence partitions.

No random split is permitted. No future partition may affect earlier scaling, encoding, candidate definition, support decisions, or estimator construction.

## Frozen estimator

For each eligible candidate and horizon, fit ordinary least squares with an intercept:

`forward_log_return ~ candidate_indicator + six frozen standardized controls`

Estimator contract:

- candidate encoding: binary indicator, `1` for the exact ordered transition and `0` otherwise;
- reference level: candidate absent;
- coefficient of interest: candidate-indicator coefficient;
- standard errors: HC3 heteroskedasticity-consistent;
- two-sided coefficient test against null `beta_candidate = 0`;
- confidence interval: two-sided 95%;
- no regularization, feature selection, interaction terms, nonlinear terms, winsorization, clipping, or hyperparameter tuning.

Report the coefficient in log-return units and `expm1(coefficient)` as an unannualized approximate percentage-return difference. This is descriptive research evidence, not a trading return.

## Multiplicity control

The single confirmatory multiplicity family contains every rankable ordered-transition-by-horizon candidate.

Apply Benjamini-Hochberg false-discovery-rate control at `q = 0.05` to the pooled controlled-estimator p-values.

Canonical results must include raw p-value, BH-adjusted q-value, coefficient, HC3 standard error, confidence interval, support counts, exclusions, and fold results.

A candidate cannot be called supported unless `q <= 0.05` and the directional-consistency rule passes.

## Directional-consistency rule

A candidate is directionally stable only when:

- both out-of-sample evaluation coefficients are finite and nonzero;
- both have the same sign;
- the pooled coefficient has that same sign.

Magnitude need not be monotonic. Statistical significance in each individual fold is not required; fold direction is a falsification gate, while pooled multiplicity-adjusted evidence is the confirmatory significance gate.

## Falsification rule

A candidate is not supported when any of the following holds:

- minimum support fails;
- either out-of-sample direction disagrees with the other or with the pooled estimate;
- incremental association relative to frozen controls is absent;
- BH-adjusted evidence exceeds `0.05`;
- the result depends on purged-out or duplicate observations;
- required exact timestamps are missing;
- leakage, source mismatch, ordering ambiguity, or non-determinism is identified;
- replay or full-suite validation fails.

Failed candidates remain visible and may not be converted into post hoc candidates.

## Required robustness and reconciliation

The implementation must verify:

- exact source and manifest identity;
- exact 242-observation purge membership;
- exact partition counts `81`, `81`, `80`;
- duplicate-anchor absence;
- strict non-`UNKNOWN` and non-self-transition eligibility;
- exact anchor and horizon matching;
- development-only scaling;
- deterministic candidate ordering and IDs;
- null and insufficient-support visibility;
- Benjamini-Hochberg implementation against a fixed test vector;
- HC3 estimator behavior against a fixed test fixture;
- two-run byte-identical replay;
- LF-only canonical text and strict JSON.

## Canonical outputs

Under `artifacts/historical_regime_transitions/`:

- `regime_transition_source_manifest.json`;
- `regime_transition_anchor_inventory.json`;
- `regime_transition_anchor_inventory.csv`;
- `regime_transition_candidate_inventory.json`;
- `regime_transition_candidate_inventory.csv`;
- `regime_transition_fold_plan.json`;
- `regime_transition_results.json`;
- `regime_transition_results.csv`;
- `regime_transition_report.md`;
- `regime_transition_manifest.json`.

All outputs must use deterministic ordering, LF line endings, strict JSON nulls, and repo-relative source identifiers.

## Acceptance evidence

Campaign #45 may be complete only when:

1. this specification and the superseding implementation handoff predate outcome generation;
2. governed identities, hashes, schemas, counts, and timestamps pass preflight;
3. the exact anchor and candidate inventories are serialized before ranking;
4. support, partition, purge, scaling, estimator, multiplicity, and direction rules reconcile exactly;
5. focused tests pass;
6. two governed runs are byte-identical;
7. canonical text is LF-only and JSON is strict;
8. governed sources remain byte-identical;
9. the full repository suite passes without new failures;
10. scope review finds no production, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes.

## Authorized implementation surfaces

After the separate implementation GO on the campaign board, Campaign #45 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- this specification;
- `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY_IMPLEMENTATION_HANDOFF.md`;
- one new observation-only module under `research/ml/validation/`;
- one new runner under `scripts/`;
- focused Campaign #45 tests under `tests/`;
- `artifacts/historical_regime_transitions/**`.

Any additional file surface requires an explicit board transition.

## Authorization boundary

This specification freezes the predictive design. It does not itself authorize runtime, strategy, signal, threshold, order, portfolio, NAV, exposure, dashboard, model-training, or production changes.