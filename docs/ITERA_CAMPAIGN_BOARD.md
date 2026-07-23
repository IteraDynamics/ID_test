# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — specification milestone complete; implementation not yet authorized

**Working branch:** `feature/core-v1-historical-event-families-spec`

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

No implementation code has been authorized on the current specification branch.

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

## Specification artifacts

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`
- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES_CADENCE_EVIDENCE.md`

Together they document:

- the exact Campaign #40 source and classified episode fields;
- the inserted zero-based `episode_id` identity contract;
- closed timestamp interval semantics for `window_start` and `window_end`;
- timestamp, rather than row-index, as the native boundary unit;
- canonical `PT1H` bar cadence with explicit missing-bar handling;
- deterministic interval-connected grouping;
- canonical SHA-256 family identity payload;
- composition-only subtype and recovery handling;
- latest, maximum, and median similarity summaries;
- exact membership, family-record, summary, and report schemas;
- fail-closed validation, replay, source-integrity, ordering, and reconciliation gates.

## Artifact reconnaissance findings

Repository inspection established:

- the source historical episode CSV contains no persisted `episode_id`;
- Campaign #40 inserts `episode_id` deterministically from zero-based persisted CSV row order;
- `window_start` and `window_end` are emitted from the prediction timestamp index;
- each interval is closed: `[window_start, window_end]`;
- the artifacts do not contain source row indices;
- `step_rows` controls rolling-window traversal and is not bar cadence;
- cadence must not be inferred from episode gaps or stream naming.

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

Immediate adjacency is finalized as:

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

## Specification acceptance gates

Completed:

1. real source identity, boundary, subtype, recovery, and similarity fields documented;
2. native boundary unit resolved as timestamp;
3. exact `btc_extended_up` cadence established as `PT1H`;
4. irregular source gaps documented and bounded by fail-closed policy;
5. immediate adjacency formula finalized;
6. canonical family identity finalized;
7. mixed subtype and recovery rules finalized;
8. family similarity fields finalized;
9. output schemas and ordering made explicit;
10. fail-closed validation rules completed;
11. no implementation code introduced.

## Milestone conclusion

The Campaign #41 specification-only milestone is complete.

Completion does not itself authorize implementation. Implementation should begin only through an explicit campaign transition that preserves this specification, creates a dedicated implementation branch or formally repurposes the current branch, and defines focused tests plus real-artifact verification evidence.

## Next executable step

Prepare the implementation-milestone handoff for deterministic event-family construction. The handoff must define the authorized files, test matrix, real-artifact commands, source-hash checks, replay checks, and non-goals before implementation code is introduced.

## Explicitly deferred

- implementation until explicitly authorized;
- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated recovery probabilities;
- deletion or mutation of existing episode artifacts;
- strategy logic;
- runtime integration;
- threshold changes;
- model retraining;
- order, NAV, or exposure mutation.

## Itera operating documents

Present on the active branch:

- `docs/ITERA_VISION.md`
- `docs/ITERA_CONSTITUTION.md`
- `docs/ITERA_RESEARCH_MANIFESTO.md`
- `docs/ITERA_RESEARCH_ROADMAP.md`
- `docs/ITERA_KNOWLEDGE_REGISTRY.md`
- `docs/ITERA_OPERATING_CADENCE.md`

These documents establish identity, governance, research philosophy, strategic direction, knowledge maturity, and calendar/campaign operating cadence. They do not authorize behavioral changes.

## Calendar operating cadence

- **Daily Mission Check:** show the current milestone finish line, required evidence, and one next action.
- **Weekly Campaign Review:** record knowledge gained, evidence, methodological risk, time allocation, and the next milestone.
- **Current finish line:** explicitly authorize and scope the implementation milestone, or pause with the completed specification.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 from the completed specification milestone. Do not introduce implementation code unless the implementation milestone is explicitly authorized and scoped. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime integration, threshold changes, model retraining, orders, NAV, or exposure mutation.

## Board maintenance rule

Update this file whenever the active campaign, branch, PR state, milestone, acceptance criteria, evidence, blocker, open decision, next executable step, or deferred scope changes.

A campaign is not considered cleanly paused until this board identifies a verified state and one concrete next executable step.
