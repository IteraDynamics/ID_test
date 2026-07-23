# Core v1 Historical Event Families — Implementation Handoff

## Campaign

**Campaign #41 — Deterministic overlap-aware historical event families**

**Milestone:** Implementation handoff only.

This document scopes and governs a later implementation milestone. It does not itself authorize code changes.

## Governing constraints

All later implementation work must remain:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- separate from production runtime;
- independent of model retraining;
- independent of threshold, order, NAV, and exposure mutation;
- additive to existing Campaign #40 artifacts;
- incapable of mutating governed source artifacts.

The normative research specification is:

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`

The governed cadence evidence is:

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`

## Authorization boundary

Implementation may begin only after an explicit Campaign Board transition authorizes the implementation milestone and names the implementation branch.

Before that transition, only documentation, review, and planning changes are authorized.

## Authorized implementation surfaces

A later implementation milestone may create or modify only the following surfaces unless the Campaign Board explicitly expands scope:

1. one research module under `research/ml/validation/` for deterministic event-family construction;
2. one command-line script under `scripts/` for real-artifact execution;
3. one focused test module under `tests/` for unit, validation, replay, and source-integrity behavior;
4. generated research artifacts under a dedicated non-runtime artifact directory;
5. Campaign #41 research documentation and the Campaign Board.

Recommended paths:

- `research/ml/validation/historical_event_families.py`;
- `scripts/run_core_v1_historical_event_families.py`;
- `tests/test_historical_event_families.py`;
- `artifacts/core_v1_historical_event_families/`.

These paths are recommendations, not authorization to implement before the Board transition.

## Prohibited surfaces

The implementation milestone must not modify:

- production runtime code;
- live state readers or writers;
- strategy logic;
- model training or retraining code;
- model thresholds;
- order generation, routing, or execution;
- portfolio construction;
- NAV calculations;
- exposure calculations or controls;
- dashboard behavior;
- existing Campaign #40 source artifacts;
- the governed prediction CSV;
- any runtime state file.

No existing artifact may be rewritten in place.

## Governed inputs

The implementation must consume and reconcile the same immutable Campaign #40 artifacts specified in the research specification:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`;
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`;
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`.

The cadence-validation source is:

- `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`.

Governed prediction-source evidence:

- SHA-256: `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`;
- row count: `52453`;
- first timestamp: `2020-01-01 01:00:00`;
- last timestamp: `2025-12-26 00:00:00`;
- timezone convention: timezone-naive;
- canonical cadence: `PT1H`;
- duplicate timestamps: zero;
- timestamp order: strictly increasing;
- irregular gaps: three two-hour gaps, one four-hour gap, and one six-hour gap.

The larger gaps are missing bars and must never be treated as alternate cadence or silently bridged.

## Required module responsibilities

The research module must provide deterministic, side-effect-free logic for:

- loading and validating governed episode rows;
- reconciling inserted zero-based `episode_id` values to persisted CSV row order;
- validating source and classified identities exactly;
- parsing and normalizing timestamp boundaries;
- validating `PT1H` against the governed prediction timestamp index;
- confirming that episode boundaries exist in the governed prediction index;
- grouping closed intervals by overlap or exactly one validated source bar;
- computing stable family identifiers;
- computing family composition and similarity summaries;
- producing canonical in-memory records suitable for strict serialization;
- failing closed on every validation violation.

The module must not perform file writes, runtime integration, network access, random sampling, or wall-clock-dependent behavior.

## Required CLI responsibilities

The command-line script must:

- accept explicit input and output paths;
- accept no hidden environment-dependent defaults for governed inputs;
- validate all sources before emitting outputs;
- compute source hashes before execution;
- invoke only the research module for grouping and record construction;
- serialize outputs with stable ordering and LF line endings;
- write only to a newly created or explicitly empty output directory;
- refuse to overwrite governed source artifacts;
- emit a machine-readable manifest containing source identities, hashes, row counts, canonical cadence, output hashes, and configuration;
- exit nonzero on any validation, reconciliation, serialization, or integrity failure.

No partial output set may be reported as successful.

## Canonical adjacency rule

For closed intervals, a later episode joins the current family only when:

`next_start <= current_family_end + PT1H`

A source timestamp gap larger than `PT1H` is preserved as a gap. No interpolation, inferred row, tolerance expansion, or learned gap rule is allowed.

## Required generated artifacts

A successful real-artifact run must emit exactly four primary artifacts plus one integrity manifest:

1. `btc_extended_up_event_family_membership.csv`;
2. `btc_extended_up_event_families.json`;
3. `btc_extended_up_event_family_summary.json`;
4. `btc_extended_up_event_family_report.md`;
5. `btc_extended_up_event_family_manifest.json`.

The first four schemas are governed by `CORE_V1_HISTORICAL_EVENT_FAMILIES.md`.

The manifest must contain at least:

- specification version;
- canonical cadence;
- normalized repository-relative source identifiers;
- SHA-256 and row count for every governed source;
- source timestamp evidence;
- output filenames and SHA-256 hashes;
- source episode count;
- event-family count;
- replay verification status;
- research-only and mutation-control flags.

All JSON must be strict JSON with sorted keys, stable separators, no NaN or Infinity, UTF-8 encoding, and a final LF.

## Focused test matrix

The focused test module must cover at least:

### Happy-path grouping

- strict overlap;
- exact one-hour adjacency;
- non-adjacency across a gap greater than one hour;
- transitive interval-connected grouping;
- canonical sort order independent of input order;
- closed-interval boundary behavior;
- exact inclusive `duration_bars`.

### Identity and reconciliation

- deterministic zero-based episode identity from persisted row order;
- duplicate episode identity rejection;
- source/classified membership mismatch rejection;
- governed-field disagreement rejection;
- incomplete or duplicate family membership rejection.

### Cadence and timestamp validation

- explicit `PT1H` acceptance;
- missing cadence rejection;
- zero or negative cadence rejection;
- inferred cadence rejection;
- non-hour-multiple timestamp delta rejection;
- duplicate prediction timestamps rejection;
- non-monotonic prediction timestamps rejection;
- malformed timestamp rejection;
- mixed timezone convention rejection;
- reversed interval rejection;
- episode boundary absent from governed prediction index rejection;
- larger missing-bar gaps preserved without adjacency expansion.

### Family identity and ordering

- canonical JSON payload construction;
- stable SHA-256 family identity;
- identifier sensitivity to membership, bounds, cadence, source identifier, and specification version;
- stable family ordering;
- stable member ordering;
- no absolute paths or operating-system-specific separators in identity payloads.

### Composition and similarity

- homogeneous subtype and recovery composition;
- mixed subtype and recovery composition;
- lexicographically ordered count dictionaries;
- latest-member deterministic tie-breaking;
- maximum similarity;
- deterministic median for odd and even member counts;
- non-finite similarity rejection.

### Serialization and integrity

- byte-identical repeated serialization;
- LF-only text outputs;
- strict JSON rejection of non-finite values;
- manifest reconciliation to all outputs;
- source hashes unchanged before and after execution;
- refusal to overwrite governed sources or a non-empty output directory.

## Real-artifact verification plan

The implementation PR must record exact executable commands after the authorized module, script, and test paths exist.

At minimum, verification must include:

1. focused tests for Campaign #41;
2. one real-artifact run against the governed inputs;
3. a second run into a separate output directory with identical inputs;
4. byte-for-byte comparison of all five generated artifacts;
5. SHA-256 checks of all governed inputs before and after both runs;
6. LF-only checks for all generated text artifacts;
7. exact reconciliation of episode membership, family records, summary, report, and manifest;
8. full repository regression tests.

A real-artifact run is not accepted if any governed source hash differs from its pre-run value.

## Replay contract

Given identical source bytes, configuration, specification version, and implementation version, two runs must produce byte-identical artifacts.

The implementation must not include:

- current timestamps;
- random identifiers;
- hostnames;
- absolute paths;
- locale-dependent formatting;
- filesystem iteration order;
- nondeterministic dictionary or set ordering;
- environment-specific line endings.

## Fail-closed contract

The CLI must exit nonzero and withhold the complete output set when any governed requirement fails.

Failure must be explicit for:

- missing or mutated sources;
- unexpected source hash or schema;
- timestamp or cadence validation failure;
- identity or membership mismatch;
- invalid interval bounds;
- invalid labels or recovery state;
- non-finite numeric input;
- non-canonical ordering;
- serialization failure;
- output hash or reconciliation mismatch;
- attempted source overwrite;
- attempted write to a prohibited surface.

The implementation must not degrade to overlap-only grouping, infer cadence, skip malformed rows, repair source data, or emit a partial success.

## Acceptance gates for implementation authorization

Before implementation begins, the Campaign Board must explicitly record:

- implementation authorized;
- implementation branch name;
- authorized file paths;
- governed input identifiers;
- canonical cadence `PT1H`;
- focused test path;
- generated artifact directory;
- real-artifact verification requirements;
- prohibited surfaces;
- merge acceptance gates.

## Merge acceptance gates

A later implementation PR may merge only when:

- the approved file scope is respected;
- focused tests pass;
- the full repository suite passes;
- real-artifact execution succeeds;
- all source identities and hashes reconcile;
- every governed episode appears exactly once in membership output;
- all family, summary, report, and manifest counts reconcile;
- replay outputs are byte-identical;
- all generated text artifacts are LF-only;
- no governed source artifact changes;
- no production runtime, threshold, model, order, NAV, or exposure behavior changes;
- the Campaign Board records exact final evidence.

## Explicit non-goals

- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated probabilities;
- dominant-label inference;
- mutation or deletion of Campaign #40 artifacts;
- strategy logic;
- runtime integration;
- threshold changes;
- model retraining;
- order, NAV, or exposure mutation;
- dashboard integration.

## Handoff conclusion

This handoff is complete when committed and reflected in `docs/ITERA_CAMPAIGN_BOARD.md`.

Completion of the handoff does not authorize implementation. The next decision is an explicit go/no-go transition into a separately governed implementation milestone.