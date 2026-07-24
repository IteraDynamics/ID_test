# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, runtime, threshold, order, NAV, exposure, model-training, or dashboard changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Draft PR open — implementation, validation, canonical artifact publication, final handoff, and scope review complete; merge remains pending explicit review and authorization

**Working branch:** `feature/core-v1-historical-event-families-implementation`

**Pull request:** Draft PR #41 — `Campaign 41: deterministic historical event families`

**Pull request URL:** `https://github.com/IteraDynamics/ID_test/pull/41`

**Repository:** `IteraDynamics/ID_test`

## Governing constraints

All work remains deterministic, replay-safe, observation-only, fail-closed, additive to Campaign #40 artifacts, separate from production runtime, independent of model retraining, and independent of threshold, order, NAV, and exposure mutation.

No merge or later campaign action may be interpreted as authorization for runtime integration or prohibited behavior changes.

## Governing documents

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_IMPLEMENTATION_HANDOFF.md`.

These govern source identities, zero-based episode identity, closed timestamp intervals, canonical `PT1H` cadence, missing-bar handling, deterministic grouping, family identity, composition, similarity, serialization, replay, publication, and fail-closed behavior.

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
- `6afed4f` — tracked the authorized Campaign #41 artifact root with `.gitkeep`;
- `d850307d53236b369af87ef5d10908d7ce0108f1` — published the five canonical Campaign #41 artifacts;
- `d9126ab4c34e6a7b89d7bf6d18c95527ce6b5f8b` — finalized the Campaign #41 implementation handoff.

The pure module remains side-effect free. The CLI requires explicit governed paths, verifies prediction identity and source hashes, recomputes and reconciles Campaign #40 classification, stages a complete deterministic output set, refuses unauthorized or non-empty output directories, and emits LF-only text artifacts.

## Canonical artifacts

Accepted canonical files under `artifacts/core_v1_historical_event_families/`:

- `btc_extended_up_event_families.json`;
- `btc_extended_up_event_family_manifest.json`;
- `btc_extended_up_event_family_membership.csv`;
- `btc_extended_up_event_family_report.md`;
- `btc_extended_up_event_family_summary.json`.

Exact canonical SHA-256 values:

- `btc_extended_up_event_families.json` — `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`;
- `btc_extended_up_event_family_manifest.json` — `e59c27fd40b4a5994cbe2b46e9585a75f8470bdcb5a9bf9998cfb32a3873da9a`;
- `btc_extended_up_event_family_membership.csv` — `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`;
- `btc_extended_up_event_family_report.md` — `f63dbb3fa66c0fb66dbcd244f0e83a890ecc011d8ac8e5c55a043e9b2638bab5`;
- `btc_extended_up_event_family_summary.json` — `cd8235ec0572060bc36872e2d6771b298d41102f91d383d5cfc4df0e0e85b922`.

The canonical set was copied from `replay_a` after exact hash and LF-only verification. `replay_a` and `replay_b` remain local validation outputs and are not committed.

## Validation evidence

### Focused suites

- original pure-core suite: `9 passed` on Windows / Python `3.14.6`;
- expanded suite: `12 passed in 1.07s` on Windows / Python `3.14.6`.

### Governed two-run execution

Both governed runs completed successfully. Each reported:

- source episodes: `122`;
- event families: `14`;
- exactly five generated outputs;
- observation-only completion;
- no runtime, threshold, order, NAV, or exposure changes.

### Replay verification

Verified across `replay_a` and `replay_b`:

- five files in each directory;
- identical filename sets;
- equal byte lengths;
- identical SHA-256 values;
- LF-only content.

### Full repository suite

Command:

`python -m pytest -q`

Result on Windows / Python `3.14.6`:

- collected: `413`;
- passed: `413`;
- failed: `0`;
- warnings: `75`;
- elapsed: `241.42s` (`0:04:01`).

Warnings were existing deprecation warnings involving `datetime.utcnow()` and pytest class-scoped instance-method fixtures.

### Publication and worktree scope

The canonical publication commit added exactly five authorized artifact files.

Local `git status --short` continued to show only pre-existing untracked export, data, server-data, and runtime-state files. None was staged or committed.

Remote comparison against `main` showed no production runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard file changes.

The branch also contains six foundational Itera governance documents created earlier on the same branch:

- `docs/ITERA_CONSTITUTION.md`;
- `docs/ITERA_KNOWLEDGE_REGISTRY.md`;
- `docs/ITERA_OPERATING_CADENCE.md`;
- `docs/ITERA_RESEARCH_MANIFESTO.md`;
- `docs/ITERA_RESEARCH_ROADMAP.md`;
- `docs/ITERA_VISION.md`.

These documentation-only files are explicitly disclosed in draft PR #41 for review.

Three accidental temporary documentation files were created and deleted during connector operation. Their net branch diff is zero; none exists in the pull request file set.

## Acceptance gates

- approved Campaign #41 implementation surfaces respected — complete;
- focused tests pass — complete;
- full repository suite passes — complete;
- real-artifact execution succeeds twice — complete;
- governed source hashes remain unchanged — complete;
- all records and counts reconcile — complete;
- all five outputs are byte-identical across replay — complete;
- all generated text artifacts are LF-only — complete;
- canonical artifacts accepted and committed — complete;
- exact hashes and final evidence recorded — complete;
- final implementation handoff updated — complete;
- branch scope reviewed — complete;
- draft pull request opened — complete;
- merge review and explicit merge authorization — pending.

## Prohibited surfaces

Do not modify production runtime code, live state, strategy logic, training code, thresholds, order generation or execution, portfolio construction, NAV, exposure controls, dashboard behavior, Campaign #40 sources, the governed prediction CSV, or runtime state files.

No existing governed artifact may be rewritten in place.

## Next executable step

Review draft PR #41, including the disclosed foundational governance documents and the Campaign #41 implementation, tests, documentation, and canonical artifacts.

Do not mark the PR ready, merge it, begin runtime integration, or start threshold, retraining, order, NAV, exposure, or dashboard work without a separate explicit authorization.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue from draft PR #41 on `feature/core-v1-historical-event-families-implementation`. Campaign #41 implementation, validation, canonical artifact publication, final handoff, and scope review are complete. Focused tests pass 12/12; the full suite passes 413/413; two governed runs each produced 122 episode memberships grouped into 14 families; all five outputs are byte-identical and LF-only; exact hashes are recorded. Review the draft PR and disclosed governance-document scope. Do not merge or introduce runtime integration, threshold changes, retraining, orders, NAV, exposure, or dashboard changes without explicit authorization.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
