# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, runtime, threshold, order, NAV, exposure, model-training, or dashboard changes.

## Active campaign

**Campaign:** Campaign #43 — Core v1 Historical Alpha Discovery

**Classification:** Research primary; deterministic predictive-signal discovery authorized

**Status:** Authorized — governing specification and implementation pending

**Working branch:** `agent/campaign-43-historical-alpha-discovery`

**Repository:** `IteraDynamics/ID_test`

## Campaign #43 exact research question

Which governed historical Core v1 episode and event-family descriptors exhibit repeatable out-of-sample association with deterministic forward BTC outcomes, after controlling for overlapping-window duplication and preserving strict research-only boundaries?

## Campaign #43 authorization

**Decision:** GO

The user explicitly authorized Campaign #43 on July 24, 2026 and requested creation of a new GitHub branch so implementation and validation can begin immediately.

Campaign #43 is the first campaign whose explicit purpose is candidate alpha discovery. It may evaluate historical predictive relationships, but it may not change production behavior or claim deployable alpha without later validation campaigns and explicit authorization.

## Campaign #43 intended output

Campaign #43 should produce a deterministic, ranked catalog of candidate historical predictors rather than a trading strategy.

Candidate results must distinguish:

- in-sample association from out-of-sample evidence;
- episode-resolution evidence from event-family-resolution evidence;
- repeated-window prevalence from independent-event support;
- direction, magnitude, horizon, and stability;
- positive evidence from null or contradictory evidence.

## Campaign #43 initial research boundary

Authorized:

- BTC only;
- existing governed Core v1 historical episodes and deterministic event families;
- deterministic forward-return and forward-path outcomes derived from governed historical market data;
- predeclared candidate descriptors already present in governed artifacts;
- deterministic chronological evaluation splits;
- observation-only candidate ranking;
- explicit null findings and falsification evidence;
- concise canonical reports and machine-readable artifacts.

Not authorized:

- production runtime integration;
- live signal generation;
- model retraining or model replacement;
- threshold changes;
- signal or intent changes;
- order generation or execution;
- portfolio construction;
- NAV changes;
- exposure mutation;
- dashboard integration;
- cross-asset work;
- transaction-cost claims;
- deployable-strategy claims;
- discretionary cherry-picking of horizons, splits, labels, or metrics after observing results.

## Campaign #43 methodological constraints

All implementation must remain deterministic, replay-safe, observation-only, and fail-closed.

The governing specification must predeclare before result inspection:

- exact governed input artifacts and hashes;
- eligible candidate descriptors;
- forward outcome definitions;
- evaluation horizons;
- chronological split construction;
- minimum support rules, if any;
- ranking metrics;
- null-handling rules;
- event-family correction rules;
- serialization and replay requirements;
- acceptance gates.

No candidate may be promoted solely because it looks favorable in one horizon, one split, or episode-resolution data while failing event-family correction.

## Campaign #43 planned canonical outputs

Under `artifacts/core_v1_historical_alpha_discovery/`:

- `btc_core_v1_alpha_candidates.json`;
- `btc_core_v1_alpha_candidates.csv`;
- `btc_core_v1_alpha_discovery_report.md`;
- `btc_core_v1_alpha_discovery_manifest.json`.

The governing specification may add a deterministic fold-level or event-family-level diagnostic artifact if required for reconciliation, but must justify it before implementation.

## Campaign #43 acceptance direction

Campaign #43 will not be accepted merely because one candidate has a positive return.

Acceptance requires, at minimum:

1. Focused Campaign #43 tests pass.
2. Full repository suite passes with no new failures.
3. Two governed runs produce byte-identical outputs.
4. Canonical text outputs are LF-only.
5. Governed source identities and hashes remain unchanged.
6. Chronological split and outcome calculations reconcile.
7. Episode and event-family evidence are both reported.
8. Null, insufficient-support, and contradictory results fail closed.
9. Scope review finds no runtime, strategy, training, threshold, order, portfolio, NAV, exposure, or dashboard changes.
10. The report makes no deployable-alpha or production recommendation.

## Campaign #43 authorized file surfaces

Initial authorization is limited to:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md`;
- `research/ml/validation/historical_alpha_discovery.py`;
- `scripts/run_core_v1_historical_alpha_discovery.py`;
- `tests/test_historical_alpha_discovery.py`;
- `artifacts/core_v1_historical_alpha_discovery/**`.

No other file surface is authorized without a later board transition.

## Campaign #42 awaiting merge

### Campaign #42 — Episode-resolution versus event-family-resolution taxonomy

**Status:** Validation complete — canonical artifacts published; PR ready for review and awaiting user merge after CI

**Working branch:** `agent/campaign-42-event-robustness`

**Pull request:** PR #42 — `Campaign 42: deterministic event robustness analysis`

**Pull request URL:** `https://github.com/IteraDynamics/ID_test/pull/42`

Campaign #42 accepted evidence:

- governed episode rows: `122`;
- deterministic event families: `14`;
- canonical outputs: `4`;
- deterministic payload digest: `0c837e746832c64b4a163ab1e968fccccf8ac338c11ce546fd08fa12278dd3b4`;
- focused suite: `7 passed in 5.82s` on Windows / Python `3.14.6`;
- full repository suite: `420 passed`, `0 failed`, `75 warnings`, `245.89s`;
- all four replay outputs byte-identical;
- all four canonical text artifacts LF-only;
- governed source hashes unchanged;
- staged Git blobs matched accepted canonical hashes;
- remote comparison found only authorized Campaign #42 surfaces.

Canonical artifact publication commit: `7be21bbdd5ee58b6044fe8ef67d1e594d6919da4`.

Campaign #42 board finalization commit: `62d51b82f30075b13e620573039e5dcc51f78065`.

No merge has been performed by the assistant. The user will merge PR #42 after required CI completes.

## Completed campaign

### Campaign #41 — Deterministic overlap-aware historical event families

**Final status:** Complete

**Pull request:** PR #41 — `Campaign 41: deterministic historical event families`

**Pull request URL:** `https://github.com/IteraDynamics/ID_test/pull/41`

**Merge method:** Squash

**Final merge SHA:** `af248fff93792100d57709df9ae1b1bc0c6a27e3`

Accepted Campaign #41 results:

- governed episode rows: `122`;
- deterministic event families: `14`;
- canonical outputs: `5`;
- observation-only: true;
- research-only: true;
- runtime integration allowed: false;
- exposure mutation allowed: false.

## Governing constraints

All work must preserve deterministic, replay-safe, observation-only, and fail-closed behavior unless a later board transition explicitly authorizes a different boundary.

Campaign #43 authorizes historical predictive research only. It does not authorize production runtime integration, model retraining, threshold changes, signal or intent changes, order generation or execution, portfolio construction, NAV changes, exposure mutation, dashboard integration, cross-asset work, or strategy deployment.

## Current implementation state

Created from the validated Campaign #42 branch head:

- branch `agent/campaign-43-historical-alpha-discovery`;
- Campaign #43 authorization boundary;
- initial canonical-output and acceptance direction.

The detailed governing specification, deterministic implementation, tests, canonical artifacts, and validation remain pending.

## Next executable step

Write `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md` with predeclared governed inputs, candidate descriptors, forward outcomes, horizons, chronological evaluation, event-family correction, ranking rules, null handling, deterministic serialization, and acceptance gates. Do not inspect or optimize results before the specification is committed.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test`. Campaign #43 is authorized and active on `agent/campaign-43-historical-alpha-discovery`. It is the first explicit historical alpha-discovery campaign, but remains deterministic, replay-safe, research-only, observation-only, and fail-closed. First commit the governing research specification before inspecting or optimizing results. Do not introduce runtime, training, threshold, signal, order, portfolio, NAV, exposure, dashboard, cross-asset, or deployable-strategy changes. Campaign #42 remains validated and awaits user merge after CI.

## Board maintenance rule

Update this file whenever campaign state, branch, PR state, milestone, acceptance evidence, blocker, decision, next executable step, or deferred scope changes.
