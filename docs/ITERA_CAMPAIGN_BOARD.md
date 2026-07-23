# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, runtime, threshold, order, NAV, exposure, model-training, or dashboard changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — deterministic core and expanded focused suite verified; two governed real-artifact runs completed successfully with identical headline counts; byte-for-byte replay comparison and full repository suite remain pending

**Working branch:** `feature/core-v1-historical-event-families-implementation`

**Pull request:** Not opened

**Repository:** `IteraDynamics/ID_test`

## Governing constraints

All work remains deterministic, replay-safe, observation-only, fail-closed, additive to Campaign #40 artifacts, separate from production runtime, independent of model retraining, and independent of threshold, order, NAV, and exposure mutation.

Authorized surfaces only:

- `research/ml/validation/historical_event_families.py`;
- `scripts/run_core_v1_historical_event_families.py`;
- `tests/test_historical_event_families.py`;
- `artifacts/core_v1_historical_event_families/`;
- Campaign #41 research documentation;
- this board.

No other implementation surface is authorized.

## Governing documents

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_IMPLEMENTATION_HANDOFF.md`.

These govern source identities, zero-based episode identity, closed timestamp intervals, canonical `PT1H` cadence, missing-bar handling, deterministic grouping, family identity, composition, similarity, serialization, replay, and fail-closed behavior.

## Governed inputs

Immutable Campaign #40 sources:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`;
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`;
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`.

Cadence-validation source:

- `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`.

Governed cadence evidence:

- SHA-256: `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`;
- rows: `52453`;
- first timestamp: `2020-01-01 01:00:00`;
- last timestamp: `2025-12-26 00:00:00`;
- timezone-naive;
- strictly increasing;
- no duplicates;
- canonical cadence: `PT1H`;
- larger deltas remain preserved missing-bar gaps.

Immediate adjacency is exactly:

`next_start <= current_family_end + PT1H`

No inferred cadence, interpolation, expanded tolerance, or learned gap rule is permitted.

## Published implementation evidence

- `405a86b` — initial deterministic event-family core;
- `1ae3298` — hardened validation and canonical construction core;
- `62d0b05` — original focused core tests;
- `124961b` — deterministic artifact runner;
- `d0ced4e` — runner-contract tests;
- `b5fd593` — exported governed `CANONICAL_BAR_CADENCE = "PT1H"`;
- `6afed4f` — tracked the authorized Campaign #41 artifact root with `.gitkeep`.

The pure module remains side-effect free. The CLI requires explicit governed paths, verifies prediction identity and source hashes, recomputes and reconciles Campaign #40 classification, stages a complete deterministic output set, refuses unauthorized or non-empty output directories, and emits LF-only text artifacts.

## Local verification evidence

### Pure-core verification

At commit `b98dc4e`:

- command: `python -m pytest -q tests/test_historical_event_families.py`;
- collected: `9`;
- passed: `9`;
- failed: `0`;
- elapsed: `3.95s`;
- environment: Windows, Python `3.14.6`.

### Expanded-suite verification

After the cadence import fix:

- command: `python -m pytest -q tests/test_historical_event_families.py`;
- collected: `12`;
- passed: `12`;
- failed: `0`;
- elapsed: `1.07s`;
- environment: Windows, Python `3.14.6`.

### Governed two-run execution

Both governed commands completed successfully into separate output directories:

- `artifacts/core_v1_historical_event_families/replay_a`;
- `artifacts/core_v1_historical_event_families/replay_b`.

Each run reported:

- source episodes: `122`;
- event families: `14`;
- observation-only completion;
- no runtime, threshold, order, NAV, or exposure changes.

Because the runner completed, its fail-closed pre-publication checks passed for each run, including governed prediction identity, input reconciliation, source-hash stability before and after execution, and complete output publication. Byte-for-byte equality between the two directories has not yet been independently demonstrated.

`git status --short` after both runs showed only the same pre-existing untracked local data and runtime files. No tracked governed source, runtime, production, or implementation file was modified by execution.

## Required generated artifacts

Each successful governed run emitted exactly:

- `btc_extended_up_event_family_membership.csv`;
- `btc_extended_up_event_families.json`;
- `btc_extended_up_event_family_summary.json`;
- `btc_extended_up_event_family_report.md`;
- `btc_extended_up_event_family_manifest.json`.

The two replay directories are validation outputs. No canonical Campaign #41 output set has yet been accepted or committed.

## Acceptance gates before merge

- expanded focused tests pass — complete;
- real-artifact execution succeeds twice into separate empty output directories — complete;
- governed source hashes remain unchanged before and after both runs — complete through runner fail-closed checks;
- membership, family records, summary, report, and manifest reconcile exactly — complete within each run through runner validation;
- all five outputs are byte-identical across replay — pending independent comparison;
- all generated text artifacts are LF-only — pending independent comparison/inspection;
- full repository suite passes — pending;
- no prohibited surface changes — maintained so far;
- exact hashes and final replay evidence are recorded here — pending.

## Prohibited surfaces

Do not modify production runtime code, live state, strategy logic, training code, thresholds, order generation or execution, portfolio construction, NAV, exposure controls, dashboard behavior, Campaign #40 sources, the governed prediction CSV, or runtime state files.

No existing artifact may be rewritten in place.

## Next executable step

Pull this board update, then independently compare the two generated directories by filename, byte length, and SHA-256. Confirm all five files are identical and contain no carriage-return bytes. Do not edit either replay directory before comparison.

After replay equality is established, run the full repository suite.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 on `feature/core-v1-historical-event-families-implementation`. The deterministic core and expanded focused suite pass. Two governed real-artifact executions completed successfully, each producing 122 episode memberships grouped into 14 event families. Independently compare all five files in `replay_a` and `replay_b` for byte-identical SHA-256 and LF-only content, then run the full repository suite. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime integration, threshold changes, retraining, orders, NAV, exposure, or dashboard changes.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
