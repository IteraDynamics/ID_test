# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, threshold, order, NAV, exposure, model-training, dashboard, or runtime changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — deterministic core locally verified; artifact CLI and expanded focused tests published, pending local verification

**Working branch:** `feature/core-v1-historical-event-families-implementation`

**Pull request:** Not opened

**Repository:** `IteraDynamics/ID_test`

**Production:** `dashboard.iteradynamics.com` / `/opt/itera/app`

## Governing constraints

All work remains:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- additive to existing Campaign #40 artifacts;
- separate from production runtime;
- independent of model retraining;
- independent of threshold, order, NAV, and exposure mutation;
- incapable of mutating governed source artifacts.

Implementation is authorized only on the named implementation branch and only within the exact file and artifact scope recorded below.

## Governing documents

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_IMPLEMENTATION_HANDOFF.md`.

These govern source identities, zero-based episode identity, closed timestamp intervals, canonical `PT1H` cadence, missing-bar handling, deterministic grouping, family identity, composition, similarity, serialization, replay, and fail-closed behavior.

## Authorization

Campaign #41 implementation is explicitly authorized on:

`feature/core-v1-historical-event-families-implementation`

Authorized surfaces:

- `research/ml/validation/historical_event_families.py`;
- `scripts/run_core_v1_historical_event_families.py`;
- `tests/test_historical_event_families.py`;
- `artifacts/core_v1_historical_event_families/`;
- Campaign #41 research documentation;
- `docs/ITERA_CAMPAIGN_BOARD.md`.

No other implementation surface is authorized.

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
- larger deltas are preserved missing-bar gaps.

Immediate adjacency is exactly:

`next_start <= current_family_end + PT1H`

No inferred cadence, interpolation, tolerance expansion, or learned gap rule is permitted.

## Published implementation evidence

Commits:

- `405a86b` — initial deterministic historical event-family core;
- `1ae3298` — hardened validation and canonical construction core;
- `62d0b05` — focused event-family core tests;
- `b98dc4e` — recorded initial core implementation progress;
- `124961b` — deterministic artifact runner;
- `d0ced4e` — artifact runner contract tests.

Implemented core responsibilities:

- zero-based episode identity insertion from persisted source row order;
- exact source/classified reconciliation;
- explicit cadence parsing;
- governed prediction timestamp validation;
- duplicate, non-monotonic, malformed, and non-multiple timestamp rejection;
- closed-interval validation;
- exact boundary membership in the governed prediction index;
- deterministic overlap and one-bar-adjacency grouping;
- stable canonical SHA-256 family identity;
- inclusive `duration_bars`;
- lexicographically ordered subtype and recovery composition;
- deterministic latest, maximum, and median similarity summaries;
- complete exactly-once membership reconciliation;
- research-only and mutation-control flags;
- no file writes, network access, randomness, runtime integration, or wall-clock behavior in the pure module.

Implemented CLI responsibilities:

- requires explicit paths for all four governed inputs, output directory, and cadence;
- enforces Campaign #41 cadence `PT1H`;
- verifies the governed prediction SHA-256, row count, and timestamp bounds;
- recomputes Campaign #40 classification from the immutable source artifacts rather than trusting an external classified file;
- reconciles classified rows exactly to persisted source episode order and fields;
- computes source hashes before execution and verifies them again before publication;
- writes through a deterministic staging directory and publishes only a complete output set;
- refuses non-empty output directories and output paths outside the authorized artifact tree;
- serializes stable LF-only CSV, JSON, and Markdown;
- emits four primary artifacts and one integrity manifest;
- records replay status as pending until a separate second run is compared.

## Local verification evidence

Command executed on Windows / Python 3.14.6:

`python -m pytest -q tests/test_historical_event_families.py`

Result captured from the user:

- collected: `9`;
- passed: `9`;
- failed: `0`;
- elapsed: `3.95s`.

This verifies commit `b98dc4e` and the original nine-test pure-core suite. It does not yet verify the later CLI commit or expanded focused tests.

`git status --short` showed only pre-existing untracked local data/runtime artifacts. No tracked governed source, runtime, or production file was modified.

## Required generated artifacts

A successful governed run must emit exactly:

- `btc_extended_up_event_family_membership.csv`;
- `btc_extended_up_event_families.json`;
- `btc_extended_up_event_family_summary.json`;
- `btc_extended_up_event_family_report.md`;
- `btc_extended_up_event_family_manifest.json`.

No real Campaign #41 output artifact has yet been accepted or committed.

## Current acceptance gates

Before real-artifact execution:

1. pull commits `124961b`, `d0ced4e`, and this Board update locally;
2. run the expanded focused suite;
3. record the exact pass/fail result;
4. correct failures without expanding authorized scope;
5. confirm tracked changes remain limited to authorized surfaces.

Before merge:

- expanded focused tests pass;
- full repository suite passes;
- real-artifact execution succeeds twice into separate output directories;
- all five outputs are byte-identical across replay;
- all generated text artifacts are LF-only;
- governed source hashes remain unchanged before and after both runs;
- membership, family records, summary, report, and manifest reconcile exactly;
- no prohibited surface changes;
- the Board records exact commands, hashes, counts, and replay evidence.

## Prohibited surfaces

Do not modify:

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
- Campaign #40 source artifacts;
- the governed prediction CSV;
- runtime state files.

No existing artifact may be rewritten in place.

## Explicit non-goals

- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated probabilities;
- dominant-label inference;
- strategy logic;
- runtime integration;
- threshold changes;
- model retraining;
- order, NAV, or exposure mutation;
- dashboard integration.

## Next executable step

Pull the latest implementation commits and execute:

`python -m pytest -q tests/test_historical_event_families.py`

Do not begin the governed real-artifact run until the expanded focused suite passes and the result is recorded.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 on `feature/core-v1-historical-event-families-implementation`. The deterministic core passed its original nine focused tests. The artifact CLI and expanded runner-contract tests are published but still require local verification. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime integration, threshold changes, model retraining, orders, NAV, exposure, or dashboard changes.

## Board maintenance rule

Update this file whenever the active campaign, branch, PR state, milestone, acceptance criteria, evidence, blocker, open decision, next executable step, or deferred scope changes.

A campaign is not considered cleanly paused until this board identifies a verified state and one concrete next executable step.
