# Campaign #46 — Full Historical Regime State Sequence Implementation Handoff

## Status

Pre-implementation handoff for `agent/campaign-46-full-regime-state-source`.

This handoff freezes exact implementation boundaries before any canonical source artifact is generated. Campaign #46 remains source-only and may not construct or inspect forward returns.

## Existing interfaces to consume unchanged

### Historical source

`data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`

Frozen identity and structure are defined in `docs/research/FULL_HISTORICAL_REGIME_STATE_SEQUENCE.md`.

### Regime engine

Import exactly:

```python
from research.regimes.baseline_engine import BaselineRegimeEngine
```

Instantiate exactly:

```python
engine = BaselineRegimeEngine()
```

Classify exactly:

```python
signals = engine.classify_dataframe(ohlcv_dataframe)
```

Do not pass alternate constructor values. Do not call private classification methods directly. Do not edit or duplicate regime logic.

## New implementation surfaces

- module: `research/ml/validation/full_historical_regime_state_sequence.py`
- runner: `scripts/run_full_historical_regime_state_sequence.py`
- focused tests: `tests/test_full_historical_regime_state_sequence.py`
- canonical directory: `artifacts/full_historical_regime_state_sequence/`

## Module responsibilities

The observation-only module must expose side-effect-free functions for:

1. validating source metadata and OHLCV structure;
2. converting the exact CSV rows into the DataFrame expected by `BaselineRegimeEngine`;
3. validating classifier defaults and frozen enum labels;
4. reconciling every returned `RegimeSignal` to its exact source row;
5. constructing state rows;
6. constructing contiguous state runs;
7. constructing ordered transition rows;
8. selecting the deterministic 168-hour purged transition set;
9. allocating purged transitions into three chronological folds;
10. constructing source-only support-feasibility summaries;
11. rendering canonical CSV, JSON, Markdown, and manifest payloads;
12. calculating deterministic SHA-256 payload and file digests.

The module must not read or write files directly except through narrowly scoped serialization helpers used by the runner. Core transformations must accept in-memory values and return in-memory values.

## Runner responsibilities

The runner must:

1. accept no alternate source path during governed execution;
2. support `--preflight-only`;
3. reject non-empty output directories;
4. capture source hashes before work;
5. run full source and classifier validation;
6. run classification and reconciliation;
7. construct all canonical payloads in a staging directory;
8. validate cross-artifact reconciliation;
9. verify source hashes remain unchanged;
10. publish by atomic staging-directory replacement;
11. emit no generated timestamp inside canonical payloads;
12. return non-zero on any mismatch.

A non-governed test-only source path may be injectable only through in-memory functions or explicit test fixtures, not through the governed CLI contract.

## Exact timestamp and gap behavior

- parse `timestamp` as timezone-naive pandas timestamps;
- preserve exact source timestamps;
- do not reindex to a complete hourly calendar;
- do not insert rows for the `30` missing timestamps;
- do not compress gaps when calculating elapsed hours;
- `duration_bars` counts observed source rows in a state run;
- elapsed timestamp fields use exact timestamp subtraction;
- transition purge requires at least `168` elapsed clock hours, not merely `168` observed rows.

## Exact state-row derivation

For each source row and corresponding `RegimeSignal`:

- `bar_index` must equal the zero-based source row position;
- `timestamp` must equal the exact source timestamp string normalized to `YYYY-MM-DDTHH:MM:SS`;
- `regime_label` is the enum value string;
- `confidence` must be finite;
- `reason` is `sub_signals["reason"]` and must be present;
- optional sub-signal numeric fields absent during warmup serialize as strict JSON `null`;
- `is_warmup` is true exactly when `regime_label == "UNKNOWN"` and `reason == "warmup"`;
- `source_row_digest` is SHA-256 over the deterministic UTF-8 encoding of the exact normalized source-row field tuple in ordered schema order.

## Exact state-run derivation

State rows are scanned in ascending `bar_index` order.

A new run begins at row zero or when `regime_label` changes from the immediately preceding observed source row. Source timestamp gaps do not by themselves start a new state run.

`state_run_id` is SHA-256 over:

`regime_label|start_bar_index|end_bar_index|start_timestamp|end_timestamp`

Run ordinals are zero-based ascending integers.

## Exact transition derivation

One transition is emitted for every adjacent observed source-row pair whose labels differ.

`transition_id` is SHA-256 over:

`prior_regime_label|current_regime_label|anchor_bar_index|anchor_timestamp`

Transitions are sorted by `(anchor_timestamp, anchor_bar_index, transition_id)` ascending and assigned zero-based ordinals after sorting.

`prior_state_duration_bars` must equal the completed prior run's duration.

`prior_transition_timestamp` references the immediately preceding transition in the complete sorted transition inventory, including transitions involving `UNKNOWN`.

`spacing_since_prior_transition_bars` is the difference between transition anchor bar indices. A separate `spacing_since_prior_transition_hours` must record exact clock-hour difference and is required for auditability.

## Exact feasibility population

The Campaign #45 feasibility population excludes any transition where either endpoint is `UNKNOWN`.

No other category is excluded.

Exact duplicate anchor timestamps are prohibited and fail closed.

The deterministic 168-hour purge operates on the complete eligible non-`UNKNOWN` transition inventory, not separately within categories.

## Exact fold allocation

Let `n` be the purged transition count.

Define:

- `base = n // 3`
- `remainder = n % 3`

Fold sizes are:

- fold 0: `base + (1 if remainder >= 1 else 0)`
- fold 1: `base + (1 if remainder >= 2 else 0)`
- fold 2: `base`

Assign ascending purged transitions contiguously to folds 0, 1, and 2.

This is a feasibility partition only, not Campaign #45's final expanding evaluation plan.

## Exact feasibility states

The summary status is assigned in this order:

1. `SOURCE_INVALID` — any governed source, classifier, schema, reconciliation, serialization, or immutability failure; publication prohibited.
2. `INSUFFICIENT_OVERALL_SUPPORT` — purged eligible transition count below 20.
3. `INSUFFICIENT_FOLD_SUPPORT` — any of the three folds contains fewer than 5 transitions.
4. `CAMPAIGN_45_SOURCE_FEASIBLE` — at least 20 overall and at least 5 in each fold.

This status says only whether a source population exists. It says nothing about predictive value.

## Canonical reconciliation requirements

The runner must verify:

- state rows equal source rows exactly;
- state-run durations sum to total state rows;
- every state row belongs to exactly one run;
- transition count equals state-run count minus one when at least one run exists;
- transition endpoints match adjacent run labels;
- transition anchors equal current-run start rows;
- purged transitions are a strict ordered subset of eligible transitions;
- every pair of consecutive purged anchors is separated by at least 168 exact hours;
- fold counts sum to purged count;
- feasibility status agrees with overall and fold counts;
- JSON and CSV representations contain identical identities and counts;
- report values reconcile to machine-readable summaries.

## Manifest requirements

The manifest must include:

- experiment name and source-only safety flags;
- exact source identity evidence;
- exact classifier file SHA-256;
- frozen classifier parameter values;
- frozen label set;
- source, state, run, transition, eligible-transition, purged-transition, and fold counts;
- gap evidence;
- canonical file names and SHA-256 values;
- deterministic aggregate payload digest;
- explicit `predictive_outcomes_generated: false`;
- explicit runtime, threshold, signal, strategy, order, portfolio, NAV, exposure, and dashboard mutation flags set to false.

## Publication protocol

- Canonical generation must use a newly created staging directory.
- Existing canonical output directories must cause failure unless explicitly empty.
- All text is written with UTF-8 and LF line endings.
- CSV uses a frozen explicit column order.
- JSON uses sorted keys, indentation of two spaces, strict nulls, and a trailing LF.
- Publication occurs only after all reconciliation and post-generation source-hash checks pass.
- A second governed run must reproduce byte-identical files.

## Preflight GO boundary

Implementation may be authorized only after this handoff and the governing specification are committed and the campaign board records a separate GO.

That GO may authorize source-only implementation, focused tests, preflight, canonical generation, replay validation, and artifact publication.

It must not authorize Campaign #45 predictive returns, estimator fitting, multiplicity testing, candidate ranking, or runtime changes.
