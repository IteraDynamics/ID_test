# Campaign #46 — Full Historical Regime State Sequence Implementation Handoff

## Status

Pre-implementation handoff for `agent/campaign-46-full-regime-state-source`.

This handoff freezes exact implementation boundaries before canonical source-artifact generation. Campaign #46 remains source-only and may not construct or inspect forward returns.

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

Do not pass alternate constructor values, call private classification methods, edit regime logic, or duplicate classifier rules.

## New implementation surfaces

- module: `research/ml/validation/full_historical_regime_state_sequence.py`
- runner: `scripts/run_full_historical_regime_state_sequence.py`
- focused tests: `tests/test_full_historical_regime_state_sequence.py`
- canonical directory: `artifacts/full_historical_regime_state_sequence/`

## Corrected source-gap evidence

The source SHA-256, byte count, row count, schema, first timestamp, and last timestamp were unchanged when governed preflight exposed a disagreement in the previously frozen missing-hour total.

A deterministic full-source diagnostic established:

- discontinuities: `14`
- missing hourly timestamps: `36`
- largest elapsed interval: `16` hours
- largest missing block: `15` timestamps

The earlier handoff reference to `30` missing timestamps is superseded. The correction was made before canonical generation and before any predictive outcome construction or inspection. It changes source metadata only and does not alter classifier logic, state definitions, transition construction, purge behavior, folds, or support gates.

## Module responsibilities

The observation-only module must provide side-effect-free functions for:

1. validating source metadata and OHLCV structure;
2. converting exact CSV rows into the classifier DataFrame;
3. validating classifier defaults and enum labels;
4. reconciling every `RegimeSignal` to its exact source row;
5. constructing state rows;
6. constructing contiguous state runs;
7. constructing ordered transition rows;
8. selecting the deterministic 168-hour purged transition set;
9. allocating purged transitions into three chronological folds;
10. constructing source-only support-feasibility summaries;
11. rendering canonical CSV, JSON, Markdown, and manifest payloads;
12. calculating deterministic SHA-256 payload and file digests.

Core transformations accept and return in-memory values. File I/O is limited to narrowly scoped runner serialization.

## Runner responsibilities

The governed runner must:

1. accept no alternate source path;
2. support `--preflight-only`;
3. reject non-empty output directories;
4. capture source identity before work;
5. validate exact source structure, including the corrected `36` missing timestamps across `14` discontinuities;
6. validate classifier defaults and labels;
7. run classification and reconciliation;
8. construct canonical payloads in a new staging directory;
9. validate cross-artifact reconciliation;
10. verify source identity remains unchanged;
11. publish by staging-directory replacement only after all checks pass;
12. emit no generated timestamp inside canonical payloads;
13. return non-zero on any mismatch.

A non-governed test source may be injected only through in-memory functions or fixtures, not through the governed CLI.

## Exact timestamp and gap behavior

- parse `timestamp` as timezone-naive pandas timestamps;
- preserve exact source timestamps;
- do not reindex to a complete hourly calendar;
- do not insert rows for the `36` missing timestamps;
- do not compress gaps when calculating elapsed hours;
- `duration_bars` counts observed rows;
- elapsed timestamp fields use exact timestamp subtraction;
- the purge requires at least `168` elapsed clock hours, not merely 168 observed rows.

## Exact state-row derivation

For each source row and corresponding `RegimeSignal`:

- `bar_index` equals the zero-based source position;
- `timestamp` equals the exact normalized source timestamp `YYYY-MM-DDTHH:MM:SS`;
- `regime_label` is the enum value string;
- `confidence` is finite;
- `reason` is present in `sub_signals`;
- absent warmup numeric sub-signals serialize as strict JSON `null`;
- `is_warmup` is true exactly for `UNKNOWN` with reason `warmup`;
- `source_row_digest` is SHA-256 over the deterministic normalized source-row tuple.

## Exact state-run derivation

State rows are scanned in ascending `bar_index`. A new run begins at row zero or when `regime_label` differs from the immediately preceding observed row. Timestamp gaps do not independently create runs.

`state_run_id` is SHA-256 over:

`regime_label|start_bar_index|end_bar_index|start_timestamp|end_timestamp`

Run ordinals are zero-based ascending integers.

## Exact transition derivation

Emit one transition for each adjacent observed-row pair whose labels differ.

`transition_id` is SHA-256 over:

`prior_regime_label|current_regime_label|anchor_bar_index|anchor_timestamp`

Transitions are sorted by `(anchor_timestamp, anchor_bar_index, transition_id)` ascending and assigned zero-based ordinals. Prior-state duration must reconcile to the completed prior run. Prior-transition spacing records both observed-bar difference and exact clock-hour difference.

## Exact feasibility population

Campaign #45 feasibility excludes transitions where either endpoint is `UNKNOWN`. No other category is excluded. Duplicate anchor timestamps fail closed.

The deterministic 168-hour purge operates on the complete eligible transition inventory, not within categories.

## Exact fold allocation

For purged count `n`:

- `base = n // 3`
- `remainder = n % 3`
- fold 0 size: `base + (1 if remainder >= 1 else 0)`
- fold 1 size: `base + (1 if remainder >= 2 else 0)`
- fold 2 size: `base`

Assign ascending purged transitions contiguously. This is a feasibility partition only.

## Exact feasibility states

Assign status in this order:

1. `SOURCE_INVALID`
2. `INSUFFICIENT_OVERALL_SUPPORT`
3. `INSUFFICIENT_FOLD_SUPPORT`
4. `CAMPAIGN_45_SOURCE_FEASIBLE`

The status concerns source support only and has no predictive meaning.

## Canonical reconciliation

The runner must verify:

- state rows equal source rows;
- state-run durations sum to all state rows;
- each state row belongs to one run;
- transition count equals run count minus one when runs exist;
- transition endpoints and anchors match adjacent runs;
- purged transitions are an ordered subset of eligible transitions;
- consecutive purged anchors are separated by at least 168 exact hours;
- fold counts sum to purged count;
- feasibility status matches counts;
- CSV, JSON, report, and manifest identities and counts reconcile.

## Manifest requirements

The manifest must include:

- source-only safety flags;
- exact source identity and corrected gap evidence;
- classifier file SHA-256;
- frozen classifier parameters and labels;
- source, state, run, transition, eligible, purged, and fold counts;
- canonical file names and SHA-256 values;
- deterministic aggregate payload digest;
- `predictive_outcomes_generated: false`;
- runtime, threshold, signal, strategy, order, portfolio, NAV, exposure, and dashboard mutation flags set to false.

## Publication protocol

- generate in a newly created staging directory;
- fail if the canonical output directory is non-empty;
- write UTF-8, LF-only text;
- use frozen CSV column order;
- use sorted strict JSON with indentation two and trailing LF;
- publish only after reconciliation and post-generation source checks pass;
- require a second governed run to reproduce byte-identical files.

## Authorization boundary

Campaign #46 authorizes source-only implementation, focused tests, preflight, canonical generation, replay validation, and artifact publication.

It does not authorize Campaign #45 predictive returns, estimator fitting, multiplicity testing, candidate ranking, model changes, or runtime changes.
