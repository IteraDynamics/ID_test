# Campaign #45 — Historical Regime State and Transition Discovery

## Status

Specification frozen for implementation review on `agent/campaign-45-historical-regime-transitions`.

Campaign #45 is research-only, observation-only, deterministic, replay-safe, and fail-closed. It does not authorize production, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes.

## Immediate objective

Freeze and test a finite inventory of anchor-local historical regime states and state transitions for incremental association with forward BTC outcomes, using deterministic event-family or chronologically separated independence controls and simple BTC price-state baselines.

The campaign asks whether historical regime state or transition information adds stable out-of-sample information beyond simple BTC price-state controls. It does not redesign or replace the existing regime detector.

## Exact research question

Across the governed historical BTC regime artifacts, do pre-registered anchor-local regime states or transitions show directionally stable, independently supported, out-of-sample association with forward BTC outcomes after comparison with simple BTC price-state baselines?

## Relationship to existing regime detection

The existing regime workflow labels historical market conditions and episodes. Campaign #45 treats those governed, time-local labels as immutable research inputs.

Campaign #45 does not:

- change how a regime is detected;
- add a new live regime;
- alter any regime threshold;
- change runtime strategy selection;
- use forward information to assign a predictor label;
- promote a historical association into a trading rule.

The new research object is the historical sequence around each anchor:

- current state;
- immediately prior state;
- ordered transition from prior state to current state;
- current-state age when safely derivable from information available at the anchor;
- transition occurrence and spacing when safely derivable from information available at the anchor.

## Governing source boundary

Eligible inputs must be repository-tracked specifications, code, schemas, manifests, or governed generated artifacts already identified by Campaign #44.

The initial governed source set is limited to:

- `docs/research/CORE_V1_HISTORICAL_REGIME_TAXONOMY.md`;
- `research/ml/validation/historical_regime_taxonomy.py`;
- `research/ml/validation/historical_regime_taxonomy_report.py`;
- `scripts/run_core_v1_historical_regime_taxonomy.py`;
- `scripts/run_core_v1_historical_regime_taxonomy_report.py`;
- governed historical event-family artifacts and schemas required to prevent overlapping episodes from being treated as independent observations;
- the governed BTC hourly close source used by prior historical research;
- Campaign #44 canonical inventory and roadmap artifacts.

Before implementation, preflight must resolve exact artifact paths, schema versions, required hashes, and timestamp semantics. If any required source identity, field meaning, or anchor timing cannot be established, the affected field or candidate must remain unavailable and the run must fail closed where necessary.

## Unit of observation and independence

The primary unit of evidence is an independent historical event family when an anchor falls inside an existing governed event family.

Rules:

1. Multiple overlapping episode rows from the same governed event family must not count as independent support.
2. When no governed event-family identity applies, observations must be chronologically separated by a pre-registered purge interval at least as long as the maximum tested outcome horizon.
3. An event family may contribute at most one observation to a given candidate, anchor definition, and horizon.
4. The deterministic representative anchor for a family must be frozen before outcome inspection.
5. Candidate support must be reported both as raw eligible anchors and independent families or purged observations.

## Frozen predictor inventory

Only the following predictor classes may be implemented. Exact field availability must be established during preflight from governed source schemas.

### P-001 Current intrinsic regime state

The anchor-local intrinsic regime label available at the observation timestamp, excluding any recovery-outcome component that depends on post-anchor information.

Eligible components may include, only when anchor-local:

- collapse severity;
- feature displacement;
- volatility-state subtype;
- composite combinations of eligible anchor-local components.

### P-002 Prior intrinsic regime state

The immediately preceding non-identical intrinsic state under a deterministic, pre-registered state-change definition.

### P-003 Ordered state transition

`<prior_intrinsic_state> -> <current_intrinsic_state>`.

Self-transitions are excluded from the primary transition inventory and may be retained only as a named baseline category.

### P-004 Current-state age

Elapsed governed rows or hours since entry into the current intrinsic state, calculated using only information available through the anchor.

State age is rankable only if state continuity and timestamp cadence can be established exactly.

### P-005 Transition spacing

Elapsed governed rows or hours since the prior eligible state transition, calculated using only information available through the anchor.

Transition spacing is rankable only if prior-transition identity is unambiguous.

### Explicitly prohibited predictors

- recovery outcome or recovery duration attached to the same episode;
- similarity to a later or latest window when that window postdates the anchor;
- any field computed with future prices or future activation behavior;
- post-anchor recovery labels;
- arbitrary combinations created after result inspection;
- learned embeddings, clustering, or model-generated transition classes;
- runtime-only fields whose historical timestamp semantics are not governed.

## Frozen simple BTC price-state controls

Each rankable regime candidate must be compared with simple anchor-local BTC controls. The implementation may use only a finite pre-registered set derived from the governed hourly close series:

1. trailing 24-hour log return;
2. trailing 72-hour log return;
3. trailing 168-hour log return;
4. trailing 24-hour realized volatility using hourly log returns;
5. trailing 168-hour realized volatility using hourly log returns;
6. distance from the trailing 168-hour close mean, normalized by trailing 168-hour close standard deviation when the denominator is finite and positive.

All trailing windows must end at or before the anchor. Missing history remains null and makes the affected row ineligible for tests requiring that control.

No control thresholds or bins may be tuned after outcome inspection. Any categorical control representation must be frozen before generation.

## Frozen outcomes and horizons

Primary outcome:

- forward BTC log return from anchor close to horizon close.

Secondary descriptive outcome:

- maximum adverse excursion over the same forward horizon, only if its exact formula is frozen before result inspection.

Frozen forward horizons:

- 24 hours;
- 72 hours;
- 168 hours.

An anchor is eligible for a horizon only when the exact anchor close and horizon close are present in the governed BTC hourly source without interpolation.

## Chronological evaluation

The study must use expanding chronological folds. Exact fold boundaries must be derived deterministically from eligible anchor timestamps before predictive outcomes are inspected.

Minimum rules:

1. At least three non-empty evaluation folds are required for a rankable candidate.
2. Training or descriptive-development periods must precede evaluation periods.
3. Purging between development and evaluation must be at least the maximum tested horizon.
4. No random split is permitted.
5. Fold boundaries and eligible counts must be serialized before candidate result summaries.
6. A candidate with insufficient independent support in any required fold remains visible but non-rankable.

## Candidate inventory and multiplicity

The candidate inventory is the Cartesian set of available frozen predictor categories and frozen horizons after fail-closed availability checks.

The implementation must:

- serialize the complete candidate inventory before result ranking;
- assign deterministic candidate IDs;
- prevent duplicated semantic candidates;
- report null and insufficient-support candidates;
- use a pre-registered multiplicity-control method for confirmatory claims;
- distinguish exploratory descriptive summaries from confirmatory supported associations.

No candidate may be added, merged, transformed, or dropped after outcome inspection except through a separately authorized campaign.

## Minimum support gates

A candidate is rankable only when all are true:

- at least 20 independent event families or purged observations overall;
- at least 5 independent observations in each required chronological evaluation fold;
- at least 5 independent observations for each side of any binary comparison;
- exact anchor-local predictor availability is established;
- no known or unresolved predictor leakage exists;
- the simple BTC control set required by the comparison is available;
- the finite falsification test can be executed without unauthorized behavior changes.

These gates control research interpretability only. They do not imply deployability or economic significance.

## Primary comparisons

For each rankable candidate and horizon, the implementation must report:

1. unconditional forward-return summary;
2. candidate-conditional forward-return summary;
3. independent-support counts;
4. fold-by-fold direction and magnitude;
5. comparison against the frozen simple BTC price-state controls;
6. incremental association after the frozen controls using a deterministic pre-registered method;
7. null, missing, and excluded counts with reasons.

The exact statistical estimator and multiplicity-control procedure must be frozen in the implementation handoff before result generation. No estimator may be selected based on observed candidate performance.

## Falsification rule

A candidate is rejected as a supported association when any of the following holds:

- direction is not stable across the required chronological evaluation folds;
- incremental association relative to frozen BTC price-state controls is absent or unstable out of sample;
- minimum independent-support gates are not met;
- the result depends on overlapping episode rows rather than independent families or purged observations;
- the result disappears under the pre-registered robustness checks;
- predictor leakage or timestamp ambiguity is identified;
- multiplicity-adjusted evidence does not meet the pre-registered confirmatory standard.

A failed candidate remains visible in canonical outputs. Failure must not be converted into a new post hoc candidate.

## Required robustness checks

The finite implementation must include:

- event-family-level versus chronologically purged observation reconciliation where both are valid;
- exclusion of recovery-dependent predictor fields;
- exact duplicate-anchor detection;
- fold-boundary and horizon-purge verification;
- simple BTC price-state control comparison;
- sensitivity to deterministic representative-anchor choice only when multiple choices were pre-registered before outcome inspection;
- null and insufficient-support visibility;
- two-run byte-identical replay.

## Canonical outputs

Planned outputs under `artifacts/historical_regime_transitions/`:

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

All canonical text outputs must use LF line endings, deterministic ordering, strict JSON nulls, and repo-relative source identifiers.

## Acceptance evidence

Campaign #45 may be considered complete only when:

1. this specification and the exact estimator handoff predate predictive-result inspection;
2. all governed source identities, hashes, schemas, and timestamp semantics pass preflight;
3. all predictor fields are proven anchor-local or excluded;
4. the finite candidate inventory is serialized deterministically;
5. overlapping episodes do not inflate independent support;
6. chronological folds and purge intervals are deterministic and validated;
7. simple BTC controls are implemented exactly as frozen;
8. focused tests cover leakage, duplicate anchors, insufficient support, fold purging, deterministic ordering, null visibility, and replay;
9. two governed runs produce byte-identical canonical outputs;
10. canonical text outputs are LF-only;
11. the full repository suite passes with no new failures;
12. scope review confirms no production, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes.

## Authorized implementation file surfaces

After a separate implementation GO recorded on the campaign board, Campaign #45 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- this specification;
- one implementation handoff under `docs/research/`;
- a new observation-only module under `research/ml/validation/`;
- a new runner under `scripts/`;
- focused Campaign #45 tests under `tests/`;
- `artifacts/historical_regime_transitions/**`.

Any additional file surface requires an explicit board transition.

## Current authorization state

The specification-only transition is authorized. Predictive-result generation, implementation, and artifact publication remain unauthorized until the exact estimator, multiplicity control, representative-anchor rule, source manifest, and preflight contract are reviewed and recorded as an implementation GO.
