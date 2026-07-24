# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #43 — Core v1 Historical Alpha Discovery

**Classification:** Research primary; deterministic historical predictive-signal discovery

**Status:** BLOCKED — governed BTC source preflight failed closed because the frozen artifact has no exact `close` column

**Working branch:** `agent/campaign-43-historical-alpha-discovery`

**Repository:** `IteraDynamics/ID_test`

## Exact research question

Which governed, anchor-available Core v1 historical descriptors exhibit repeatable out-of-sample association with deterministic forward BTC outcomes after correcting overlapping-window duplication through deterministic event families?

## Authorization

**Decision:** GO for research design and source diagnosis; predictive result generation remains prohibited until a valid price source is explicitly governed.

The user explicitly authorized Campaign #43 on July 24, 2026. It may evaluate and rank historical predictive relationships for later falsification. It may not alter production behavior or claim deployable alpha.

## Governing constraints

All work must remain deterministic, replay-safe, research-only, observation-only, and fail-closed.

Campaign #43 does not authorize production runtime integration, model training or replacement, threshold/signal/intent changes, orders or execution, portfolio construction, NAV or exposure changes, dashboards, cross-asset work, transaction-cost claims, deployable-alpha claims, or strategy recommendations.

## Frozen specification

- Governing document: `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md`
- Specification freeze commit: `57472a2fc4594e9d4e9ea1681cecef8d0c15dc25`

The specification froze, before predictive result inspection:

- governed source paths, hashes, counts, and timestamp evidence;
- candidate inventory and leakage exclusions;
- episode and event-family anchors;
- homogeneous-only family aggregation;
- exact forward outcomes and exact `close` requirement;
- horizons `2`, `6`, `24`, `72`, and `168` hours;
- three deterministic expanding chronological folds;
- support gates, evidence states, ranking tuple, canonical outputs, and replay rules.

No frozen research decision may change after result inspection without an explicit board transition and separately designated rerun.

## Leakage controls

Rankable descriptors are limited to:

1. `collapse_severity`;
2. `feature_displacement`;
3. `volatility_state`;
4. `intrinsic_subtype`.

Excluded as predictors:

- `recovery_outcome`, `recovered_without_retraining`, and `recovery_rows`, because they use information observed after the episode anchor;
- `feature_cosine_similarity_to_latest` and `similarity_band`, because the reference is not anchor-local;
- IDs, ordinals, timestamps, source positions, arbitrary interactions, and post-result transformations.

## Frozen governed inputs

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`
  - SHA-256 `0c1ebc70007570cb7172f2a46283ab25128e1911ac34f447cc5f306c211d3a17`
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`
  - SHA-256 `6eaadd0fd6d2231d517e5062f15bf5ea92f6bd40e3a1b1aded415e891596c143`; `122` rows
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`
  - SHA-256 `ccb0b748b82f7a6449b9caf945b904bfaa4871cdf2a35413c9157c41890e2327`; `122` rows
- `artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json`
  - SHA-256 `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`; `14` families
- `artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv`
  - SHA-256 `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`; `122` memberships
- `artifacts/core_v1_event_robustness/btc_extended_up_event_robustness.json`
  - SHA-256 `578d8e7c0176489ff5b67761b48ece8bac3285ba06b70ae6ee5d8fe93abb0dc7`
- `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`
  - SHA-256 `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`; `52,453` rows; `2020-01-01 01:00:00` through `2025-12-26 00:00:00`

The frozen hourly artifact was required to contain an exact finite, strictly positive `close` column. No alternate field, interpolation, filling, resampling, or inferred source is authorized.

## Source preflight blocker

User-run preflight evidence on July 24, 2026:

- branch HEAD: `496a8b8471b601060e98f9a9e25d24e4a36be4bc`;
- command: `python scripts/run_core_v1_historical_alpha_discovery.py --preflight-only`;
- result: failed closed in `validate_price_series`;
- exact error: `governed BTC series must contain exact close column`.

This is an accepted safety outcome, not an implementation bypass request. No predictive outcomes, rankings, or canonical Campaign #43 result artifacts were generated or inspected.

A replacement or additional price source may not be selected implicitly. The source schema may be inspected observation-only. Any proposed price source must then receive an explicit board transition recording its repository-relative path, SHA-256, timestamp convention, row count, price field, and reconciliation rule before result generation.

## Current implementation and validation state

Completed:

- Campaign #43 branch and authorization boundary;
- frozen governing specification;
- leakage-prone candidates excluded;
- pure validation/calculation primitives;
- focused unit tests;
- governed source preflight runner;
- source mutation detection;
- explicit preflight-only safety flag;
- fail-closed discovery that the frozen prediction artifact is not a governed close-price source.

Key commits:

- specification freeze: `57472a2fc4594e9d4e9ea1681cecef8d0c15dc25`;
- pure primitives: `e462c91628136d7429c58e4706da7a3a7d484b30`;
- focused tests: `e41320c192f6223f5e707aed82ed80a1b59647ac`;
- source preflight runner: `9810a88360dbda6bb3901f0052e3caa2f3e0a41e`.

Accepted focused-test evidence:

- Windows / Python `3.14.6`;
- `8 passed in 5.71s`;
- failures: `0`.

## Authorized file surfaces

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md`;
- `research/ml/validation/historical_alpha_discovery.py`;
- `scripts/run_core_v1_historical_alpha_discovery.py`;
- `tests/test_historical_alpha_discovery.py`;
- `artifacts/core_v1_historical_alpha_discovery/**`.

No other file surface is authorized without a board transition.

## Planned canonical outputs

Under `artifacts/core_v1_historical_alpha_discovery/`:

- `btc_core_v1_alpha_candidates.json`;
- `btc_core_v1_alpha_candidates.csv`;
- `btc_core_v1_alpha_discovery_folds.csv`;
- `btc_core_v1_alpha_discovery_report.md`;
- `btc_core_v1_alpha_discovery_manifest.json`.

## Acceptance gates

1. Frozen specification predates predictive result inspection.
2. Focused Campaign #43 tests pass.
3. A valid governed BTC close-price source passes explicit path/hash/schema/timestamp/count preflight.
4. Full repository suite passes with no new failures.
5. Two governed runs produce byte-identical outputs.
6. Canonical text outputs are LF-only.
7. Governed source identities and hashes remain unchanged.
8. Episode, event-family, mixed-family, unavailable-outcome, and fold counts reconcile.
9. Chronological folds contain no look-ahead.
10. Null, insufficient-support, contradictory, unstable, and unavailable evidence remain visible and fail closed.
11. Scope review finds no runtime, strategy, training, threshold, signal, order, portfolio, NAV, exposure, dashboard, or cross-asset changes.
12. The report makes no deployable-alpha or production recommendation.

## Campaign #42 awaiting merge

**Status:** Validation complete; canonical artifacts published; PR #42 ready for user merge after CI.

**Branch:** `agent/campaign-42-event-robustness`

**PR:** `https://github.com/IteraDynamics/ID_test/pull/42`

Accepted evidence includes `122` episodes, `14` families, `4` canonical outputs, focused suite `7 passed`, full suite `420 passed`, byte-identical replay, LF-only outputs, and unchanged governed source hashes.

Campaign #42 publication commit: `7be21bbdd5ee58b6044fe8ef67d1e594d6919da4`.

Campaign #42 board finalization commit: `62d51b82f30075b13e620573039e5dcc51f78065`.

No merge was performed by the assistant.

## Completed campaign

### Campaign #41 — Deterministic overlap-aware historical event families

**Final status:** Complete

**PR:** `https://github.com/IteraDynamics/ID_test/pull/41`

**Merge method:** Squash

**Final merge SHA:** `af248fff93792100d57709df9ae1b1bc0c6a27e3`

Accepted results include `122` governed episodes and `14` deterministic event families.

## Next executable step

Inspect only the frozen CSV schema and a single non-result sample row. Do not calculate returns, inspect candidate associations, or substitute another field.

Run:

`python -c "import pandas as pd; p=r'artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv'; d=pd.read_csv(p, nrows=1); print('COLUMNS:', list(d.columns)); print('SAMPLE:', d.iloc[0].to_dict())"`

Report the complete output. This observation-only inspection determines whether the artifact contains a clearly named price field or only model predictions. A new governed price source still requires an explicit board transition.

Do not stage unrelated local runtime/data files.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`. Campaign #43 is blocked after a correct fail-closed preflight: the frozen 52,453-row BTC artifact does not contain exact `close`. Focused tests passed `8 passed in 5.71s` on Windows/Python `3.14.6`. No predictive results were generated or inspected. The next step is observation-only schema inspection of the frozen CSV, followed by an explicit board transition if a different governed close-price source is required. Preserve deterministic, replay-safe, research-only, observation-only, and fail-closed behavior. Do not change runtime, training, thresholds, signals, orders, portfolio, NAV, exposure, dashboards, cross-asset scope, or the frozen research design.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
