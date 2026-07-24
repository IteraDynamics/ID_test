# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, runtime, threshold, order, NAV, exposure, model-training, or dashboard changes.

## Active campaign

**Campaign:** Campaign #42 — Episode-resolution versus event-family-resolution taxonomy

**Classification:** Research primary; engineering deferred

**Status:** Planning only — Campaign #41 is complete and merged; Campaign #42 research question, specification, inputs, schemas, acceptance gates, branch, and implementation scope remain unapproved

**Working branch:** None authorized

**Pull request:** None

**Repository:** `IteraDynamics/ID_test`

## Completed campaign

### Campaign #41 — Deterministic overlap-aware historical event families

**Final status:** Complete

**Pull request:** PR #41 — `Campaign 41: deterministic historical event families`

**Pull request URL:** `https://github.com/IteraDynamics/ID_test/pull/41`

**Merge method:** Squash

**Final merge SHA:** `af248fff93792100d57709df9ae1b1bc0c6a27e3`

Campaign #41 implementation, validation, canonical artifact publication, final handoff, branch-scope review, PR review, and merge are complete.

## Governing constraints

All subsequent work must preserve deterministic, replay-safe, observation-only, and fail-closed behavior unless a later board transition explicitly authorizes a different research boundary.

Campaign #41 closure and Campaign #42 planning do not authorize production runtime integration, model retraining, threshold changes, order generation or execution, portfolio construction, NAV changes, exposure mutation, or dashboard integration.

## Campaign #41 governing documents

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_IMPLEMENTATION_HANDOFF.md`.

## Campaign #41 accepted evidence

Governed inputs remained unchanged:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`;
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`;
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`;
- `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`.

Canonical cadence:

- `PT1H`;
- immediate adjacency: `next_start <= current_family_end + PT1H`;
- no inferred cadence, interpolation, expanded tolerance, or learned gap rule.

Accepted results:

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

Canonical artifacts under `artifacts/core_v1_historical_event_families/`:

- `btc_extended_up_event_families.json` — `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`;
- `btc_extended_up_event_family_manifest.json` — `e59c27fd40b4a5994cbe2b46e9585a75f8470bdcb5a9bf9998cfb32a3873da9a`;
- `btc_extended_up_event_family_membership.csv` — `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`;
- `btc_extended_up_event_family_report.md` — `f63dbb3fa66c0fb66dbcd244f0e83a890ecc011d8ac8e5c55a043e9b2638bab5`;
- `btc_extended_up_event_family_summary.json` — `cd8235ec0572060bc36872e2d6771b298d41102f91d383d5cfc4df0e0e85b922`.

Publication commit on the working branch:

- `d850307d53236b369af87ef5d10908d7ce0108f1`.

Final implementation handoff commit:

- `90435f80840bae2881e38e5e036655378d21ad78`.

Final merged Campaign #41 state:

- `af248fff93792100d57709df9ae1b1bc0c6a27e3`.

## Campaign #42 provisional research question

Compare the governed Core v1 descriptive taxonomy at episode resolution versus independent event-family resolution.

Planning should determine:

- which subtype and recovery distributions materially change after overlap de-duplication;
- whether repeated episode windows overstate the apparent prevalence of particular historical structures;
- which descriptive findings remain stable across both resolutions;
- how mixed-label event families should be represented without dominant-label inference;
- which conclusions are unsupported because the effective independent-event count is only `14`;
- whether Campaign #42 should remain BTC-only or include a separately governed portability phase.

## Campaign #42 authorization boundary

No Campaign #42 code, generated artifact, branch, pull request, runtime integration, threshold change, retraining, order, NAV, exposure, or dashboard work is authorized.

Before implementation, the board must explicitly record:

1. the exact research question and non-goals;
2. governed input identities and hashes;
3. episode-resolution and family-resolution counting rules;
4. mixed-label representation rules;
5. output schemas and artifact paths;
6. deterministic serialization and replay requirements;
7. focused and full-suite acceptance gates;
8. authorized file surfaces;
9. implementation branch;
10. explicit go/no-go authorization.

## Next executable step

Discuss and specify Campaign #42 at the research-design level only.

The preferred first decision is whether Campaign #42 should be:

- a narrow BTC-only descriptive comparison using existing Campaign #40 and #41 artifacts; or
- a broader comparison that also prepares, but does not yet execute, cross-asset portability work.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`. Campaign #41 is complete and was squash-merged through PR #41 at `af248fff93792100d57709df9ae1b1bc0c6a27e3`. Campaign #42 is planning-only and provisionally compares the Core v1 taxonomy at episode resolution versus independent event-family resolution. Do not implement, create a branch, generate artifacts, or introduce runtime, threshold, retraining, order, NAV, exposure, or dashboard changes until the Campaign #42 specification and authorization gates are explicitly approved.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
