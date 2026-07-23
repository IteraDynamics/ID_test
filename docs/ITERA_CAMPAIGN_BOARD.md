# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — specification reconnaissance complete except cadence evidence

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

No implementation code is authorized during the current specification-only milestone.

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

## Specification artifact

Updated:

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`

The specification now documents:

- the exact Campaign #40 source and classified episode fields;
- the inserted zero-based `episode_id` identity contract;
- closed timestamp interval semantics for `window_start` and `window_end`;
- timestamp, rather than row-index, as the native boundary unit;
- explicit validated `bar_cadence` as the only permitted adjacency unit;
- deterministic interval-connected grouping;
- canonical SHA-256 family identity payload;
- composition-only subtype and recovery handling;
- latest, maximum, and median similarity summaries;
- exact membership, family-record, summary, and report schemas;
- complete fail-closed validation requirements;
- replay, source-integrity, ordering, and reconciliation gates.

## Artifact reconnaissance findings

Repository inspection established:

- the source historical episode CSV contains no persisted `episode_id`;
- Campaign #40 inserts `episode_id` deterministically from zero-based persisted CSV row order;
- `window_start` and `window_end` are emitted from the prediction timestamp index;
- each interval is closed: `[window_start, window_end]`;
- the artifacts do not contain source row indices;
- `step_rows` controls rolling-window traversal and is not bar cadence;
- no governed Campaign #40 artifact encodes the prediction bar cadence;
- cadence must not be inferred from episode gaps or stream naming.

Therefore immediate adjacency is specified as:

`next_start <= current_family_end + bar_cadence`

where `bar_cadence` must be explicit, positive, canonical, and validated against the governed prediction timestamp source. Missing or irregular cadence evidence is a fail-closed blocker.

## Finalized specification decisions

- **Episode identity:** integer `episode_id` assigned from persisted source CSV row order and reconciled exactly across artifacts.
- **Boundaries:** normalized closed timestamp intervals using `window_start` and `window_end`.
- **Adjacency:** overlap or exactly one validated source bar cadence; no implicit tolerance.
- **Intrinsic subtype:** `collapse_severity + feature_displacement + volatility_state`.
- **Recovery:** complete `recovery_outcome` composition only.
- **Dominant labels:** not emitted.
- **Similarity:** latest-member, maximum, and median similarity-to-current.
- **Family identity:** SHA-256 of strict canonical JSON containing specification version, normalized source identifier, canonical cadence, family bounds, and ordered episode identities.

## Itera operating documents

Present on the active branch:

- `docs/ITERA_VISION.md`
- `docs/ITERA_CONSTITUTION.md`
- `docs/ITERA_RESEARCH_MANIFESTO.md`
- `docs/ITERA_RESEARCH_ROADMAP.md`
- `docs/ITERA_KNOWLEDGE_REGISTRY.md`
- `docs/ITERA_OPERATING_CADENCE.md`

These documents establish identity, governance, research philosophy, strategic direction, knowledge maturity, and calendar/campaign operating cadence. They do not authorize behavioral changes.

## Current milestone acceptance gates

Completed:

1. real source identity, boundary, subtype, recovery, and similarity fields documented;
2. native boundary unit resolved as timestamp;
3. immediate adjacency formula defined exactly;
4. canonical family identity finalized;
5. mixed subtype and recovery rules finalized;
6. family similarity fields finalized;
7. output schemas and ordering made explicit;
8. fail-closed validation rules completed;
9. no implementation code introduced.

Remaining:

10. establish the exact `btc_extended_up` bar cadence from the governed prediction timestamp source and document validation evidence.

## Current blocker

The committed Campaign #40 artifacts and code do not encode the prediction bar cadence. The local data-bearing checkout must identify the exact prediction CSV used for the historical analysis and inspect its timestamp index.

This is an evidence requirement, not authorization to modify the prediction source.

## First executable step

On the real data-bearing checkout, identify the `btc_extended_up.csv` prediction file passed through `--predictions-dir` when producing `btc_extended_up_historical_regimes.json`. Inspect the timestamp index for:

- timezone convention;
- minimum, maximum, and unique consecutive deltas;
- duplicate timestamps;
- monotonic ordering;
- any irregular gaps.

Record the exact source path, SHA-256, row count, first timestamp, last timestamp, and cadence evidence. Then update the specification and this board. Do not implement event-family code yet.

## Explicitly deferred

- event-family implementation during the current milestone;
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

## Calendar operating cadence

- **Daily Mission Check:** show the current specification finish line, required evidence, and one next action.
- **Weekly Campaign Review:** record knowledge gained, evidence, methodological risk, time allocation, and the next milestone.
- **Current finish line:** establish and validate the governed `btc_extended_up` prediction cadence.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 from the cadence-evidence gate. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce implementation code, runtime integration, threshold changes, model retraining, orders, NAV, or exposure mutation unless explicitly authorized.

## Board maintenance rule

Update this file whenever the active campaign, branch, PR state, milestone, acceptance criteria, evidence, blocker, open decision, next executable step, or deferred scope changes.

A campaign is not considered cleanly paused until this board identifies a verified state and one concrete next executable step.
