# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state and authorization record. It does not authorize production, threshold, order, NAV, exposure, model-training, dashboard, or runtime changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — implementation milestone explicitly authorized within the exact scope below

**Working branch:** `feature/core-v1-historical-event-families-implementation`

**Pull request:** Not opened

**Repository:** `IteraDynamics/ID_test`

**Production:** `dashboard.iteradynamics.com` / `/opt/itera/app`

## Governing constraints

All work remains:

- deterministic;
- replay-safe;
- observation-only;
- fail-closed;
- additive to existing Campaign #40 artifacts;
- separate from production runtime;
- independent of model retraining;
- independent of threshold, order, NAV, and exposure mutation;
- incapable of mutating governed source artifacts.

Implementation is authorized only on the named implementation branch and only within the exact file and artifact scope recorded below.

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

## Implementation authorization

Campaign #41 implementation is explicitly authorized on:

`feature/core-v1-historical-event-families-implementation`

Authorization is limited to these repository surfaces:

- `research/ml/validation/historical_event_families.py`;
- `scripts/run_core_v1_historical_event_families.py`;
- `tests/test_historical_event_families.py`;
- generated research artifacts under `artifacts/core_v1_historical_event_families/`;
- Campaign #41 research documentation;
- `docs/ITERA_CAMPAIGN_BOARD.md`.

No other code, artifact, runtime, model, portfolio, or dashboard surface is authorized without a new explicit Board transition.

## Governed inputs

Implementation must consume and reconcile these immutable Campaign #40 artifacts:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`;
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`;
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`.

Cadence validation must use:

- `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv`.

The governed cadence is exactly `PT1H`. It must not be inferred from episode gaps, filenames, stream names, or `step_rows`.

## Required implementation outputs

A successful real-artifact run must emit exactly four primary artifacts plus one integrity manifest under a dedicated non-runtime output directory:

- `btc_extended_up_event_family_membership.csv`;
- `btc_extended_up_event_families.json`;
- `btc_extended_up_event_family_summary.json`;
- `btc_extended_up_event_family_report.md`;
- `btc_extended_up_event_family_manifest.json`.

All output schemas, ordering, identity payloads, and serialization rules are governed by the Campaign #41 specification and implementation handoff.

## Focused test and verification requirements

The focused test path is:

`tests/test_historical_event_families.py`

Implementation acceptance requires:

1. focused happy-path, identity, cadence, timestamp, ordering, family-ID, composition, similarity, serialization, replay, overwrite-protection, and source-integrity tests;
2. one real-artifact run against the governed inputs;
3. a second run into a separate output directory with identical inputs;
4. byte-for-byte comparison of all five generated artifacts;
5. SHA-256 checks of all governed inputs before and after both runs;
6. LF-only checks for all generated text artifacts;
7. exact reconciliation of membership, family records, summary, report, and manifest;
8. full repository regression tests.

A real-artifact run fails if any governed source hash changes, any output is partial, any output directory is non-empty without explicit safe handling, or any validation is skipped or repaired silently.

## Prohibited surfaces

Implementation must not modify:

- production runtime code;
- live state readers or writers;
- strategy logic;
- model training or retraining code;
- model thresholds;
- order generation, routing, or execution;
- portfolio construction;
- NAV calculations;
- exposure calculations or controls;
- dashboard behavior;
- existing Campaign #40 source artifacts;
- the governed prediction CSV;
- any runtime state file.

No existing artifact may be rewritten in place. No runtime, threshold, order, NAV, exposure, model, dashboard, or production behavior change is authorized.

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
11. implementation handoff completed with file-scope recommendations, test matrix, artifact contract, and verification gates;
12. implementation milestone explicitly authorized on the named implementation branch within the exact scope above.

## Current implementation milestone

The current milestone is to implement the deterministic, side-effect-free event-family construction module and its focused tests.

The first executable engineering task is:

1. create `research/ml/validation/historical_event_families.py` with pure validation, reconciliation, grouping, identity, composition, and similarity logic;
2. create `tests/test_historical_event_families.py` covering the focused deterministic and fail-closed matrix;
3. do not create the CLI or real artifacts until the module and focused tests are stable and reviewed.

## Merge acceptance gates

The implementation PR may merge only when:

- the approved file scope is respected;
- focused tests pass;
- the full repository suite passes;
- real-artifact execution succeeds;
- all source identities and hashes reconcile;
- every governed episode appears exactly once in membership output;
- all family, summary, report, and manifest counts reconcile;
- replay outputs are byte-identical;
- all generated text artifacts are LF-only;
- no governed source artifact changes;
- no prohibited production, runtime, threshold, model, order, NAV, exposure, or dashboard behavior changes;
- this Board records exact final evidence.

## Explicitly deferred

- learned clustering;
- semantic or model-generated event labels;
- predictive recovery modeling;
- calibrated recovery probabilities;
- dominant-label inference;
- mutation or deletion of Campaign #40 artifacts;
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
- **Current finish line:** pure event-family module plus focused tests, with no CLI, generated artifacts, or prohibited-surface changes yet.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 on `feature/core-v1-historical-event-families-implementation`. Implementation is authorized only within the exact Board and handoff scope. Begin with the deterministic, side-effect-free event-family module and focused tests. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce runtime integration, threshold changes, model retraining, orders, NAV, exposure, dashboard behavior, or mutation of governed source artifacts.

## Board maintenance rule

Update this file whenever the active campaign, branch, PR state, milestone, acceptance criteria, evidence, blocker, open decision, next executable step, or deferred scope changes.

A campaign is not considered cleanly paused until this board identifies a verified state and one concrete next executable step.
