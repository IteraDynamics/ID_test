# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — implementation handoff complete; implementation not yet authorized

**Working branch:** `feature/core-v1-historical-event-families-handoff`

**Pull request:** Not opened

**Repository:** `IteraDynamics/ID_test`

**Production:** `dashboard.iteradynamics.com` / `/opt/itera/app`

## Governing constraints

All work remains:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- separate from production runtime;
- independent of model retraining;
- independent of threshold, order, NAV, and exposure mutation.

No implementation code has been authorized on the current handoff branch.

## Campaign #40 closeout

PR #40, **Core v1 Historical Regime Taxonomy**, has been merged into `main`.

Final verified evidence:

- 13 focused tests passed;
- 122 real classified episodes;
- taxonomy digest: `2114b2353322b3404db4000b36e425716c1a6d01027934ac0b0f595c9f45484f`;
- report digest: `e1b29df5853e86c8da627730f2a4af374c0e64c58889f0f0dfdb601385581618`;
- five generated artifacts were byte-identical across replay and LF-only;
- three source artifacts retained identical SHA-256 hashes;
- full repository suite: 401 passed, 75 existing warnings, exit code 0;
- no Core state, thresholds, runtime, NAV, orders, or exposure changed.

The principal methodological limitation carried forward is that many classified episode rows arise from overlapping rolling windows and are dependent observations.

## Current research question

Can overlapping or immediately adjacent historical collapse episode windows be grouped into deterministic, replay-safe event families so Itera can report both episode-level and event-family-level descriptive results without mutating existing episode artifacts?

## Governing Campaign #41 documents

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`;
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_IMPLEMENTATION_HANDOFF.md`.

Together they govern:

- source and classified episode fields;
- inserted zero-based `episode_id` identity;
- closed timestamp intervals;
- canonical `PT1H` cadence and missing-bar policy;
- deterministic interval-connected grouping;
- stable family identity;
- composition and similarity summaries;
- output schemas and ordering;
- fail-closed validation;
- authorized implementation surfaces;
- focused tests;
- real-artifact, replay, line-ending, reconciliation, and source-integrity gates;
- prohibited production and portfolio surfaces.

## Cadence evidence

The inspected governed prediction source is:

`artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`

Evidence:

- SHA-256: `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7`;
- 52,453 rows;
- first timestamp: `2020-01-01 01:00:00`;
- last timestamp: `2025-12-26 00:00:00`;
- timezone-naive;
- strictly monotonic increasing;
- zero duplicate timestamps;
- 52,447 one-hour deltas;
- three two-hour gaps;
- one four-hour gap;
- one six-hour gap.

Determination:

- canonical bar cadence is `PT1H`;
- the five larger deltas are missing-bar gaps, not alternate cadence;
- larger source gaps are not silently bridged;
- every accepted timestamp delta must be a positive integer multiple of `PT1H`;
- episode boundaries must exist in the governed timestamp index.

Immediate adjacency is:

`next_start <= current_family_end + PT1H`

No implicit tolerance, interpolation, inferred rows, or learned gap rule is permitted.

## Finalized specification decisions

- **Episode identity:** integer `episode_id` assigned from persisted source CSV row order and reconciled exactly across artifacts.
- **Boundaries:** normalized closed timestamp intervals using `window_start` and `window_end`.
- **Adjacency:** overlap or exactly one `PT1H` source bar; no implicit tolerance.
- **Missing bars:** preserved as gaps and never synthesized or treated as adjacency beyond `PT1H`.
- **Intrinsic subtype:** `collapse_severity + feature_displacement + volatility_state`.
- **Recovery:** complete `recovery_outcome` composition only.
- **Dominant labels:** not emitted.
- **Similarity:** latest-member, maximum, and median similarity-to-current.
- **Family identity:** SHA-256 of strict canonical JSON containing specification version, normalized source identifier, canonical cadence, family bounds, and ordered episode identities.

## Implementation handoff

The handoff is complete and defines the later implementation boundary.

Recommended implementation surfaces:

- `research/ml/validation/historical_event_families.py`;
- `scripts/run_core_v1_historical_event_families.py`;
- `tests/test_historical_event_families.py`;
- `artifacts/core_v1_historical_event_families/`.

Required outputs:

- `btc_extended_up_event_family_membership.csv`;
- `btc_extended_up_event_families.json`;
- `btc_extended_up_event_family_summary.json`;
- `btc_extended_up_event_family_report.md`;
- `btc_extended_up_event_family_manifest.json`.

The handoff requires focused happy-path, identity, cadence, timestamp, ordering, family-ID, composition, similarity, serialization, replay, overwrite-protection, and source-integrity tests.

Real-artifact verification must include two independent output directories, byte-identical replay, LF-only text artifacts, exact reconciliation, source hashes before and after execution, and the full repository suite.

## Completed milestones

1. source identity, boundaries, subtype, recovery, and similarity documented;
2. native boundary unit resolved as timestamp;
3. exact cadence established as `PT1H`;
4. irregular gaps documented and governed;
5. adjacency formula finalized;
6. family identity finalized;
7. composition and similarity rules finalized;
8. output schemas and ordering finalized;
9. fail-closed rules finalized;
10. specification milestone completed without implementation code;
11. implementation handoff completed with authorized-surface recommendations, test matrix, artifact contract, and verification gates.

## Current authorization state

Implementation remains unauthorized.

The handoff document is a scope contract, not permission to write code. A new explicit Board transition must authorize implementation and name the implementation branch before any module, script, test, or generated artifact code is introduced.

## Next executable step

Review the implementation handoff and make an explicit go/no-go decision.

If authorized, the Board transition must record:

- implementation authorized;
- implementation branch;
- exact authorized files;
- governed inputs and `PT1H` cadence;
- focused test path;
- output artifact directory;
- real-artifact and replay commands;
- source-integrity checks;
- merge gates;
- prohibited surfaces.

If not authorized, pause Campaign #41 with the completed specification and handoff documents.

## Explicitly deferred

- implementation until explicitly authorized;
- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated recovery probabilities;
- dominant-label inference;
- deletion or mutation of existing episode artifacts;
- strategy logic;
- runtime integration;
- threshold changes;
- model retraining;
- order, NAV, or exposure mutation;
- dashboard integration.

## Itera operating documents

Present on the active branch:

- `docs/ITERA_VISION.md`;
- `docs/ITERA_CONSTITUTION.md`;
- `docs/ITERA_RESEARCH_MANIFESTO.md`;
- `docs/ITERA_RESEARCH_ROADMAP.md`;
- `docs/ITERA_KNOWLEDGE_REGISTRY.md`;
- `docs/ITERA_OPERATING_CADENCE.md`.

These documents establish identity, governance, research philosophy, strategic direction, knowledge maturity, and calendar/campaign operating cadence. They do not authorize behavioral changes.

## Calendar operating cadence

- **Daily Mission Check:** show the current milestone finish line, required evidence, and one next action.
- **Weekly Campaign Review:** record knowledge gained, evidence, methodological risk, time allocation, and the next milestone.
- **Current finish line:** explicit implementation go/no-go decision.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 from the completed implementation handoff. Do not introduce implementation code unless the Board explicitly authorizes the implementation milestone and names its branch and file scope. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime integration, threshold changes, model retraining, orders, NAV, or exposure mutation.

## Board maintenance rule

Update this file whenever the active campaign, branch, PR state, milestone, acceptance criteria, evidence, blocker, open decision, next executable step, or deferred scope changes.

A campaign is not considered cleanly paused until this board identifies a verified state and one concrete next executable step.