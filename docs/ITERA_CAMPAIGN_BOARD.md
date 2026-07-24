# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, runtime, threshold, order, NAV, exposure, model-training, or dashboard changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Closure authorized — implementation, validation, canonical artifact publication, documentation, scope review, and draft-PR review complete; PR #41 is authorized for squash merge

**Working branch:** `feature/core-v1-historical-event-families-implementation`

**Pull request:** PR #41 — `Campaign 41: deterministic historical event families`

**Pull request URL:** `https://github.com/IteraDynamics/ID_test/pull/41`

**Repository:** `IteraDynamics/ID_test`

## Governing constraints

All work remains deterministic, replay-safe, observation-only, fail-closed, additive to Campaign #40 artifacts, separate from production runtime, independent of model retraining, and independent of threshold, order, NAV, and exposure mutation.

Campaign closure and merge do not authorize runtime integration or any prohibited behavior change.

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
- `d9126ab4c34e6a7b89d7bf6d18c95527ce6b5f8b` — finalized the Campaign #41 implementation handoff;
- `e02950aa2e39026dcc2208a19f100dc3c2b10b5d` — recorded Campaign #41 knowledge gain and the proposed Campaign #42 frontier.

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

- focused suite: `12 passed in 1.07s` on Windows / Python `3.14.6`;
- full repository suite: `413 passed`, `0 failed`, `75 warnings`, `241.42s`;
- two governed runs completed successfully;
- each run reconciled `122` governed episodes into `14` event families;
- each run emitted exactly five outputs;
- all replay filenames, byte lengths, and SHA-256 values matched;
- all generated text artifacts were LF-only;
- governed source identities and hashes remained unchanged;
- publication staged and committed exactly five authorized canonical artifacts;
- local unrelated runtime, server-data, export, and manifest files remained untracked and untouched;
- remote scope review found no production runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard file changes.

The branch also contains six foundational Itera governance documents created earlier on the same branch. They are documentation-only and were explicitly disclosed in PR #41.

Three accidental temporary documentation files were created and deleted during connector operation. Their net branch diff is zero; none exists in the pull-request file set. Squash merge is selected so those transient commits do not enter `main` history.

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
- draft pull request opened and reviewed — complete;
- Campaign #41 closure and squash merge — authorized.

## Prohibited surfaces

Do not modify production runtime code, live state, strategy logic, training code, thresholds, order generation or execution, portfolio construction, NAV, exposure controls, dashboard behavior, Campaign #40 sources, the governed prediction CSV, or runtime state files.

No existing governed artifact may be rewritten in place.

## Next executable step

Squash-merge PR #41 into `main`, verify the merged state, record the final merge SHA here, and transition the board to Campaign #41 complete / Campaign #42 planning.

Campaign #42 is not yet authorized for implementation. The provisional research frontier is comparison of the Core v1 taxonomy at episode resolution versus independent event-family resolution, as recorded in `docs/ITERA_RESEARCH_ROADMAP.md`.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`. Campaign #41 implementation, validation, canonical artifact publication, documentation, and scope review are complete, and PR #41 is authorized for squash merge. After merge, record the merge SHA and transition to Campaign #42 planning only. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime integration, threshold changes, retraining, orders, NAV, exposure, or dashboard changes.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
