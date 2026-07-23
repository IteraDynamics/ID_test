# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is descriptive project state. It does not authorize production, threshold, order, NAV, exposure, or runtime changes.

## Active campaign

**Campaign:** Campaign #41 — Deterministic overlap-aware historical event families

**Classification:** Research primary; engineering secondary

**Status:** Active — specification-only milestone opened

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

Created:

- `docs/research/CORE_V1_HISTORICAL_EVENT_FAMILIES.md`

The initial specification defines:

- interval-connected event-family grouping;
- stable ordering and identity requirements;
- exact source membership requirements;
- mixed subtype and recovery composition handling;
- latest-window similarity requirements;
- strict output and replay requirements;
- fail-closed validation;
- explicit deferred scope.

## Itera operating documents

Created on the active branch:

- `docs/ITERA_VISION.md`
- `docs/ITERA_CONSTITUTION.md`
- `docs/ITERA_RESEARCH_MANIFESTO.md`
- `docs/ITERA_RESEARCH_ROADMAP.md`
- `docs/ITERA_KNOWLEDGE_REGISTRY.md`
- `docs/ITERA_OPERATING_CADENCE.md`

These documents establish identity, governance, research philosophy, strategic direction, knowledge maturity, and calendar/campaign operating cadence. They do not authorize behavioral changes.

## Current milestone acceptance gates

The specification-only milestone is complete when:

1. real source boundary fields and units are documented;
2. immediate adjacency is defined exactly;
3. canonical family identity is finalized;
4. mixed subtype and recovery rules are finalized;
5. family similarity summary fields are finalized;
6. output schemas and ordering are explicit;
7. fail-closed validation rules are complete;
8. verification commands and evidence requirements are documented;
9. no implementation code has been introduced.

## Open decisions

- Which real source fields define episode identity, start, and end boundaries?
- Is immediate adjacency expressed by row index or expected bar cadence?
- Should event families expose a dominant subtype/recovery label, or composition only?
- Which similarity statistics accompany the required latest-window similarity?
- What exact canonical payload produces the stable family identifier?

No decision may be resolved by an implicit tolerance, incidental ordering, learned clustering, or undocumented heuristic.

## First executable step

Inspect the three Campaign #40 source artifacts and the existing taxonomy implementation to document the exact episode identity, boundary, subtype, recovery, and similarity fields. Resolve the native adjacency unit from those governed inputs, then update the specification.

## Explicitly deferred

- implementation during the current milestone;
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
- **Current finish line:** document the governed source schema and finalize exact interval adjacency.

## New-chat handoff prompt

> Open `docs/ITERA_CAMPAIGN_BOARD.md` in `IteraDynamics/ID_test` and continue Campaign #41 from the documented specification-only milestone. Preserve deterministic, replay-safe, observation-only, and fail-closed behavior. Do not introduce implementation code, runtime integration, threshold changes, model retraining, orders, NAV, or exposure mutation unless explicitly authorized.

## Board maintenance rule

Update this file whenever the active campaign, branch, PR state, milestone, acceptance criteria, evidence, blocker, open decision, next executable step, or deferred scope changes.

A campaign is not considered cleanly paused until this board identifies a verified state and one concrete next executable step.