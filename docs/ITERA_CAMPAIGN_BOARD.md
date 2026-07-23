# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, runtime, threshold, order, NAV, exposure, model-training, or dashboard changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — implementation and all validation gates complete; canonical artifact acceptance, artifact commit scope, and pull-request publication remain pending explicit authorization

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

## Validation evidence

### Focused suites

- original pure-core suite: `9 passed` on Windows / Python `3.14.6`;
- expanded suite: `12 passed in 1.07s` on Windows / Python `3.14.6`.

### Governed two-run execution

Both governed commands completed successfully into:

- `artifacts/core_v1_historical_event_families/replay_a`;
- `artifacts/core_v1_historical_event_families/replay_b`.

Each run reported:

- source episodes: `122`;
- event families: `14`;
- observation-only completion;
- no runtime, threshold, order, NAV, or exposure changes.

The runner's fail-closed checks passed within each run, including governed prediction identity, input reconciliation, source-hash stability, and complete output publication.

### Replay verification

A corrected PowerShell comparison used absolute paths, strict mode, terminating errors, filename-set checks, byte-length checks, SHA-256 checks, and carriage-return-byte checks.

Verified:

- replay A files: `5`;
- replay B files: `5`;
- identical filename sets;
- equal byte lengths for every file;
- identical SHA-256 values for every file;
- LF-only content in both directories.

Exact accepted replay hashes:

- `btc_extended_up_event_families.json` — `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`;
- `btc_extended_up_event_family_manifest.json` — `e59c27fd40b4a5994cbe2b46e9585a75f8470bdcb5a9bf9998cfb32a3873da9a`;
- `btc_extended_up_event_family_membership.csv` — `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`;
- `btc_extended_up_event_family_report.md` — `f63dbb3fa66c0fb66dbcd244f0e83a890ecc011d8ac8e5c55a043e9b2638bab5`;
- `btc_extended_up_event_family_summary.json` — `cd8235ec0572060bc36872e2d6771b298d41102f91d383d5cfc4df0e0e85b922`.

### Full repository suite

Command:

`python -m pytest -q`

Result on Windows / Python `3.14.6`:

- collected: `413`;
- passed: `413`;
- failed: `0`;
- warnings: `75`;
- elapsed: `241.42s` (`0:04:01`).

Warnings were existing deprecation warnings involving `datetime.utcnow()` and pytest class-scoped instance-method fixtures. No test failed.

### Worktree status

Final `git status --short` showed only the same pre-existing untracked local export, data, server-data, and runtime-state files. No tracked governed source, generated replay artifact, production, runtime, threshold, order, NAV, exposure, model-training, or dashboard file was modified by validation.

## Required generated artifacts

Each successful governed run emitted exactly:

- `btc_extended_up_event_family_membership.csv`;
- `btc_extended_up_event_families.json`;
- `btc_extended_up_event_family_summary.json`;
- `btc_extended_up_event_family_report.md`;
- `btc_extended_up_event_family_manifest.json`.

The two replay directories remain validation outputs. No canonical Campaign #41 output set has yet been explicitly accepted or committed.

## Acceptance gates before merge

- expanded focused tests pass — complete;
- real-artifact execution succeeds twice into separate empty output directories — complete;
- governed source hashes remain unchanged before and after both runs — complete;
- membership, family records, summary, report, and manifest reconcile within each run — complete;
- all five outputs are byte-identical across replay — complete;
- all generated text artifacts are LF-only — complete;
- full repository suite passes — complete;
- no prohibited surface changes — complete;
- exact hashes and final replay evidence are recorded here — complete.

All technical validation gates are complete. This does not itself authorize canonical artifact selection, artifact movement or copying, artifact commit, branch merge, pull-request opening, or any production/runtime integration.

## Prohibited surfaces

Do not modify production runtime code, live state, strategy logic, training code, thresholds, order generation or execution, portfolio construction, NAV, exposure controls, dashboard behavior, Campaign #40 sources, the governed prediction CSV, or runtime state files.

No existing artifact may be rewritten in place.

## Next executable step

Await explicit authorization for the publication decision:

1. whether one byte-identical replay set should be accepted as the canonical Campaign #41 artifact set;
2. the exact canonical destination within `artifacts/core_v1_historical_event_families/`;
3. whether generated artifacts should be committed on the working branch;
4. whether to open a pull request after final scope review.

Until authorized, do not copy, rename, delete, move, or commit either replay directory and do not open or merge a pull request.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 on `feature/core-v1-historical-event-families-implementation`. All implementation and validation gates pass: focused suite 12/12, full suite 413/413, two governed runs each produced 122 episode memberships grouped into 14 families, and all five files are byte-identical and LF-only with exact hashes recorded on the board. Await explicit authorization before selecting or committing a canonical artifact set or opening a pull request. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime integration, threshold changes, retraining, orders, NAV, exposure, or dashboard changes.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
