# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, or cross-asset changes.

## Active campaign

**Campaign:** Campaign #43 — Core v1 Historical Alpha Discovery

**Classification:** Research primary; deterministic historical predictive-signal discovery

**Status:** Governing specification frozen — source preflight and implementation pending

**Working branch:** `agent/campaign-43-historical-alpha-discovery`

**Repository:** `IteraDynamics/ID_test`

## Exact research question

Which governed, anchor-available Core v1 historical descriptors exhibit repeatable out-of-sample association with deterministic forward BTC outcomes after correcting overlapping-window duplication through deterministic event families?

## Authorization

**Decision:** GO, subject to source preflight.

The user explicitly authorized Campaign #43 on July 24, 2026. Campaign #43 is the first campaign whose explicit purpose is candidate alpha discovery.

It may evaluate historical predictive relationships and rank candidates for later falsification. It may not alter production behavior or claim deployable alpha.

## Frozen governing specification

The governing pre-registration is committed at:

- `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md`
- specification commit: `57472a2fc4594e9d4e9ea1681cecef8d0c15dc25`

The specification freezes before predictive result inspection:

- exact governed source paths, hashes, row/count evidence, and timestamp evidence;
- rankable candidate inventory;
- explicit look-ahead exclusions;
- episode and event-family anchors;
- homogeneous-only event-family candidate aggregation;
- exact forward outcomes and price-selection rule;
- horizons `2`, `6`, `24`, `72`, and `168` hours;
- three deterministic expanding chronological folds;
- support gates;
- evidence states;
- deterministic ranking tuple;
- canonical outputs and replay requirements.

No frozen research decision may change after result inspection without an explicit board transition and separately designated rerun.

## Important leakage decision

`recovery_outcome`, `recovered_without_retraining`, and `recovery_rows` are excluded as Campaign #43 predictors because they use information observed after the episode `window_end` anchor.

`feature_cosine_similarity_to_latest` and `similarity_band` are also excluded because their reference is not an anchor-local historical quantity.

Initial rankable descriptors are limited to:

1. `collapse_severity`;
2. `feature_displacement`;
3. `volatility_state`;
4. `intrinsic_subtype`.

## Frozen governed inputs

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`
  - SHA-256: `0c1ebc70007570cb7172f2a46283ab25128e1911ac34f447cc5f306c211d3a17`
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`
  - SHA-256: `6eaadd0fd6d2231d517e5062f15bf5ea92f6bd40e3a1b1aded415e891596c143`
  - rows: `122`
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`
  - SHA-256: `ccb0b748b82f7a6449b9caf945b904bfaa4871cdf2a35413c9157c41890e2327`
  - rows: `122`
- `artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json`
  - SHA-256: `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`
  - families: `14`
- `artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv`
  - SHA-256: `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`
  - memberships: `122`
- `artifacts/core_v1_event_robustness/btc_extended_up_event_robustness.json`
  - SHA-256: `578d8e7c0176489ff5b67761b48ece8bac3285ba06b70ae6ee5d8fe93abb0dc7`
- `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`
  - SHA-256: `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`
  - rows: `52,453`
  - first timestamp: `2020-01-01 01:00:00`
  - last timestamp: `2025-12-26 00:00:00`

The hourly BTC artifact must contain an exact finite, strictly positive `close` column. No alternate field, interpolation, filling, resampling, or inferred market source is authorized. Absence or mismatch blocks result generation and requires a board transition.

## Intended output

Campaign #43 produces a deterministic ranked catalog of candidate historical associations, including null, unstable, contradictory, insufficient-support, and unavailable results.

It does not produce a trading strategy.

## Canonical outputs

Under `artifacts/core_v1_historical_alpha_discovery/`:

- `btc_core_v1_alpha_candidates.json`;
- `btc_core_v1_alpha_candidates.csv`;
- `btc_core_v1_alpha_discovery_folds.csv`;
- `btc_core_v1_alpha_discovery_report.md`;
- `btc_core_v1_alpha_discovery_manifest.json`.

## Authorized file surfaces

Authorization is limited to:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md`;
- `research/ml/validation/historical_alpha_discovery.py`;
- `scripts/run_core_v1_historical_alpha_discovery.py`;
- `tests/test_historical_alpha_discovery.py`;
- `artifacts/core_v1_historical_alpha_discovery/**`.

No other file surface is authorized without a later board transition.

## Acceptance gates

1. Frozen specification predates predictive result inspection.
2. Focused Campaign #43 tests pass.
3. Full repository suite passes with no new failures.
4. Two governed runs produce byte-identical outputs.
5. Canonical text outputs are LF-only.
6. Governed source identities and hashes remain unchanged.
7. Episode, event-family, mixed-family, unavailable-outcome, and fold counts reconcile.
8. Chronological folds contain no look-ahead.
9. Null, insufficient-support, contradictory, unstable, and unavailable evidence remain visible and fail closed.
10. Scope review finds no runtime, strategy, training, threshold, signal, order, portfolio, NAV, exposure, dashboard, or cross-asset changes.
11. The report makes no deployable-alpha or production recommendation.

## Campaign #42 awaiting merge

**Campaign:** Campaign #42 — Episode-resolution versus event-family-resolution taxonomy

**Status:** Validation complete; canonical artifacts published; PR #42 ready for user merge after CI

**Branch:** `agent/campaign-42-event-robustness`

**PR:** `https://github.com/IteraDynamics/ID_test/pull/42`

Accepted evidence:

- governed episode rows: `122`;
- deterministic event families: `14`;
- canonical outputs: `4`;
- deterministic payload digest: `0c837e746832c64b4a163ab1e968fccccf8ac338c11ce546fd08fa12278dd3b4`;
- focused suite: `7 passed`;
- full repository suite: `420 passed`, `0 failed`;
- replay outputs byte-identical;
- canonical text artifacts LF-only;
- governed source hashes unchanged.

Campaign #42 publication commit: `7be21bbdd5ee58b6044fe8ef67d1e594d6919da4`.

Campaign #42 board finalization commit: `62d51b82f30075b13e620573039e5dcc51f78065`.

No merge was performed by the assistant.

## Completed campaign

### Campaign #41 — Deterministic overlap-aware historical event families

**Final status:** Complete

**PR:** `https://github.com/IteraDynamics/ID_test/pull/41`

**Merge method:** Squash

**Final merge SHA:** `af248fff93792100d57709df9ae1b1bc0c6a27e3`

Accepted results include `122` governed episode rows and `14` deterministic event families, with observation-only and research-only boundaries preserved.

## Governing constraints

All work must preserve deterministic, replay-safe, observation-only, and fail-closed behavior.

Campaign #43 authorizes historical predictive research only. It does not authorize production runtime integration, model training, threshold changes, signals, intents, orders, execution, portfolio construction, NAV changes, exposure mutation, dashboards, cross-asset work, or strategy deployment.

## Current implementation state

Completed:

- Campaign #43 branch created;
- authorization boundary committed;
- exact governing research specification frozen;
- leakage-prone candidate fields excluded;
- fold diagnostic output authorized.

Pending:

- deterministic source/schema preflight;
- implementation;
- focused tests;
- governed artifact generation;
- replay and full-suite validation.

## Next executable step

Implement `research/ml/validation/historical_alpha_discovery.py` beginning with deterministic source/schema preflight and pure calculation functions. Add focused tests before running governed predictive results. Fail closed if the exact governed BTC source or exact `close` column is unavailable. Do not inspect, optimize, or revise the frozen candidate, horizon, fold, support, state, or ranking rules based on results.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`. Campaign #43 is active on `agent/campaign-43-historical-alpha-discovery`. The governing historical alpha-discovery specification is frozen at commit `57472a2fc4594e9d4e9ea1681cecef8d0c15dc25`. Preserve deterministic, replay-safe, research-only, observation-only, and fail-closed behavior. Implement source/schema preflight and pure functions first, with focused tests before governed result generation. Fail closed if the exact governed BTC source or `close` column is unavailable. Do not alter runtime, training, thresholds, signals, orders, portfolio, NAV, exposure, dashboards, cross-asset scope, or the frozen research design.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
