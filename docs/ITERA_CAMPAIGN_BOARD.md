# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, runtime, threshold, order, NAV, exposure, model-training, or dashboard changes.

## Active campaign

**Campaign:** Campaign #42 — Episode-resolution versus event-family-resolution taxonomy

**Classification:** Research primary; deterministic descriptive engineering authorized

**Status:** Validation complete — canonical artifacts published; PR ready for review

**Working branch:** `agent/campaign-42-event-robustness`

**Pull request:** PR #42 — `Campaign 42: deterministic event robustness analysis` (ready for review)

**Pull request URL:** `https://github.com/IteraDynamics/ID_test/pull/42`

**Repository:** `IteraDynamics/ID_test`

## Campaign #42 exact research question

How do governed Core v1 intrinsic-subtype and recovery-outcome descriptions change when measured as overlapping episode observations versus label presence within deterministic historical event families?

## Campaign #42 authorization

**Decision:** GO

The user explicitly authorized Campaign #42 implementation on July 24, 2026.

Authorized scope is a narrow BTC-only descriptive comparison using existing Campaign #41 canonical artifacts. Cross-asset portability is deferred.

## Campaign #42 governing document

- `docs/research/CORE_V1_EVENT_ROBUSTNESS.md`.

## Campaign #42 governed inputs

- `artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json` — `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`;
- `artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv` — `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`.

The implementation records exact source hashes in its manifest, verifies them before and after generation, and fails closed on disagreement.

## Campaign #42 counting rules

Episode resolution:

- each governed episode contributes exactly one intrinsic-subtype observation;
- each governed episode contributes exactly one recovery-outcome observation.

Event-family presence resolution:

- each family contributes at most one presence observation per label contained in its governed Campaign #41 count map;
- mixed families may contribute presence to multiple labels;
- family-presence shares are descriptive prevalence values and need not sum to one.

Event-family homogeneous resolution:

- a family contributes only when exactly one label is present in the corresponding count map.

Mixed-label rule:

- mixed families remain mixed;
- no dominant, plurality, latest, weighted, or inferred family label may be created.

## Campaign #42 measurements

For each intrinsic-subtype and recovery-outcome label:

- episode count and share;
- event-family presence count and share;
- event-family homogeneous count and share;
- family-presence share minus episode share;
- episode amplification ratio: episode count divided by family-presence count.

No materiality threshold, confidence category, significance test, predictive claim, or alpha conclusion is authorized.

## Campaign #42 canonical outputs

Under `artifacts/core_v1_event_robustness/`:

- `btc_extended_up_event_robustness.json` — `578d8e7c0176489ff5b67761b48ece8bac3285ba06b70ae6ee5d8fe93abb0dc7`;
- `btc_extended_up_event_robustness_labels.csv` — `106a792f6dd822a4d2419c53f6296d1c9c80e7504ec4199d74b3afde5bbcb4cd`;
- `btc_extended_up_event_robustness_report.md` — `26c556b70b4d4f1d52903ff93cf5fc6e4a1f2ab27358670fca15ccb085080ec3`;
- `btc_extended_up_event_robustness_manifest.json` — `956b5f74a3182389849263f3043790398b3ed06e733893e87cbe8fc586f0ada5`.

Canonical artifact publication commit: `7be21bbdd5ee58b6044fe8ef67d1e594d6919da4`.

## Campaign #42 serialization and replay requirements

- deterministic sorting;
- strict JSON with sorted keys and no NaN;
- LF-only text;
- no generated timestamp in canonical payloads;
- deterministic payload digest;
- newly created or explicitly empty output directory only;
- staging-directory publication;
- no governed-source overwrite;
- source hashes unchanged before and after generation;
- two governed runs must be byte-identical.

## Campaign #42 accepted results

- governed episode rows: `122`;
- deterministic event families: `14`;
- canonical outputs: `4`;
- deterministic payload digest: `0c837e746832c64b4a163ab1e968fccccf8ac338c11ce546fd08fa12278dd3b4`;
- research-only: true;
- observation-only: true;
- runtime integration allowed: false;
- exposure mutation allowed: false.

Validation:

- focused suite: `7 passed in 5.82s` on Windows / Python `3.14.6`;
- full repository suite: `420 passed`, `0 failed`, `75 warnings`, `245.89s`;
- both governed source hashes verified before generation;
- two governed real-artifact runs completed successfully;
- all four replay outputs were byte-identical;
- all four canonical text artifacts were LF-only;
- output schemas and counts reconciled at `122` episodes and `14` event families;
- governed source identities and hashes remained unchanged after generation;
- staged Git blobs were LF-only and matched accepted canonical hashes;
- remote comparison against `main` found only authorized Campaign #42 file surfaces and no runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard file changes.

## Campaign #42 acceptance gates

1. Focused Campaign #42 tests pass. — **Passed**
2. Full repository suite passes with no new failures. — **Passed**
3. Two governed runs produce byte-identical outputs. — **Passed**
4. Canonical text outputs are LF-only. — **Passed**
5. Governed source identities and hashes remain unchanged. — **Passed**
6. Output schemas and counts reconcile. — **Passed**
7. Scope review finds no runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard changes. — **Passed**

## Campaign #42 authorized file surfaces

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/CORE_V1_EVENT_ROBUSTNESS.md`;
- `research/ml/validation/event_robustness.py`;
- `scripts/run_core_v1_event_robustness.py`;
- `tests/test_event_robustness.py`;
- `artifacts/core_v1_event_robustness/**`.

No other file surface is authorized without a later board transition.

## Governing constraints

All work must preserve deterministic, replay-safe, observation-only, and fail-closed behavior unless a later board transition explicitly authorizes a different boundary.

Campaign #42 does not authorize production runtime integration, model retraining, threshold changes, signal or intent changes, order generation or execution, portfolio construction, NAV changes, exposure mutation, dashboard integration, cross-asset work, predictive claims, statistical-independence claims, or strategy recommendations.

## Completed campaign

### Campaign #41 — Deterministic overlap-aware historical event families

**Final status:** Complete

**Pull request:** PR #41 — `Campaign 41: deterministic historical event families`

**Pull request URL:** `https://github.com/IteraDynamics/ID_test/pull/41`

**Merge method:** Squash

**Final merge SHA:** `af248fff93792100d57709df9ae1b1bc0c6a27e3`

Campaign #41 implementation, validation, canonical artifact publication, final handoff, branch-scope review, PR review, and merge are complete.

Accepted Campaign #41 results:

- governed episode rows: `122`;
- deterministic event families: `14`;
- canonical outputs: `5`;
- observation-only: true;
- research-only: true;
- runtime integration allowed: false;
- exposure mutation allowed: false.

Validation:

- focused suite: `12 passed in 1.07s` on Windows / Python `3.14.6`;
- full repository suite: `413 passed`, `0 failed`, `75 warnings`, `241.42s`;
- two governed real-artifact runs completed successfully;
- all five replay outputs were byte-identical;
- all generated text artifacts were LF-only;
- governed source identities and hashes remained unchanged;
- remote scope review found no production runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard file changes.

## Current implementation state

Committed on `agent/campaign-42-event-robustness`:

- governing specification;
- deterministic validation and aggregation engine;
- canonical artifact runner;
- focused synthetic tests;
- four governed canonical artifacts;
- accepted validation and scope-review evidence;
- PR #42 ready for review.

No merge has been authorized or performed.

## Next executable step

Review PR #42. Merge only after explicit user authorization and any required review or CI checks pass. Do not begin Campaign #43 or change runtime, training, threshold, signal, order, portfolio, NAV, exposure, dashboard, cross-asset, predictive, or strategy behavior without a later explicit board transition.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`. Campaign #41 is complete and merged at `af248fff93792100d57709df9ae1b1bc0c6a27e3`. Campaign #42 validation is complete on `agent/campaign-42-event-robustness`; PR #42 is ready for review. All seven acceptance gates passed, four governed canonical artifacts were published, and the branch-scope review found only authorized file surfaces. Review PR #42 and merge only after explicit authorization. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime, training, threshold, signal, order, portfolio, NAV, exposure, dashboard, cross-asset, predictive, or strategy changes.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
