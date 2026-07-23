# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is a descriptive project-state and authorization record. It does not authorize production, runtime, threshold, order, NAV, exposure, model-training, or dashboard changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — artifact CLI implementation published; expanded focused suite blocked at collection by a missing exported cadence constant; compatibility fix published and pending local verification

**Working branch:** `feature/core-v1-historical-event-families-implementation`

**Pull request:** Not opened

**Repository:** `IteraDynamics/ID_test`

## Governing constraints

All work remains:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- additive to Campaign #40 artifacts;
- separate from production runtime;
- independent of model retraining;
- independent of threshold, order, NAV, and exposure mutation;
- incapable of mutating governed source artifacts.

Implementation is authorized only on the named branch and only within:

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

These govern source identities, zero-based episode identity, closed timestamp intervals, canonical `PT1H` cadence, missing-bar handling, grouping, family identity, composition, similarity, serialization, replay, and fail-closed behavior.

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
- `b98dc4e` — recorded initial core progress;
- `124961b` — deterministic artifact runner;
- `d0ced4e` — runner-contract tests;
- `4322d05` — recorded CLI milestone;
- `b5fd593` — exported governed `CANONICAL_BAR_CADENCE = "PT1H"` required by the runner import contract.

The pure module remains side-effect free. The CLI requires explicit governed paths, verifies prediction identity and source hashes, recomputes and reconciles Campaign #40 classification, stages a complete deterministic output set, refuses unauthorized or non-empty output directories, and emits LF-only text artifacts.

## Local verification evidence

### Pure-core verification

Command:

`python -m pytest -q tests/test_historical_event_families.py`

At commit `b98dc4e`:

- collected: `9`;
- passed: `9`;
- failed: `0`;
- elapsed: `3.95s`;
- environment: Windows, Python `3.14.6`.

### Expanded-suite collection failure

After pulling through `4322d05`, the same command produced:

- collected: `0`;
- collection errors: `1`;
- failing import: `scripts/run_core_v1_historical_event_families.py`;
- cause: `CANONICAL_BAR_CADENCE` was imported from `research.ml.validation.historical_event_families` but not exported there.

This was a module/runner contract omission, not an executed grouping or artifact-generation failure. Commit `b5fd593` adds only the governed constant `CANONICAL_BAR_CADENCE = "PT1H"`; no algorithm, cadence value, threshold, runtime, order, NAV, or exposure behavior changed.

The user's `git status --short` was empty after the failed run. No tracked or untracked changes were reported in that invocation.

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

1. pull commit `b5fd593` and this Board update;
2. rerun `python -m pytest -q tests/test_historical_event_families.py`;
3. record the exact result;
4. correct any remaining failure without expanding scope;
5. confirm tracked changes remain limited to authorized surfaces.

Before merge:

- expanded focused tests pass;
- full repository suite passes;
- real-artifact execution succeeds twice into separate empty output directories;
- all five outputs are byte-identical across replay;
- all generated text artifacts are LF-only;
- governed source hashes remain unchanged before and after both runs;
- membership, family records, summary, report, and manifest reconcile exactly;
- no prohibited surface changes;
- exact commands, hashes, counts, and replay evidence are recorded here.

## Prohibited surfaces

Do not modify production runtime code, live state, strategy logic, training code, thresholds, order generation or execution, portfolio construction, NAV, exposure controls, dashboard behavior, Campaign #40 sources, the governed prediction CSV, or runtime state files.

No existing artifact may be rewritten in place.

## Explicit non-goals

Learned clustering, generated event labels, predictive recovery modeling, calibrated probabilities, dominant-label inference, runtime integration, model retraining, threshold changes, orders, NAV, exposure mutation, and dashboard integration remain out of scope.

## Next executable step

Pull the compatibility fix and rerun:

```powershell
git pull --ff-only
python -m pytest -q tests/test_historical_event_families.py
git status --short
```

Do not begin the governed real-artifact run until the expanded focused suite passes and the result is recorded.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 on `feature/core-v1-historical-event-families-implementation`. The pure core previously passed nine tests. The expanded suite then failed during collection because the runner imported a missing governed cadence constant. Commit `b5fd593` fixes that contract and awaits local verification. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime integration, threshold changes, retraining, orders, NAV, exposure, or dashboard changes.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
