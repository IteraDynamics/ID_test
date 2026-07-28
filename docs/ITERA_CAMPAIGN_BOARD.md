# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`: Itera Dynamics is building an institutional-grade quantitative investment firm. That thesis is directional context only and does not modify any active campaign authorization.

Beginning with Campaign #44, every campaign proposal must state its immediate objective, acceptance evidence, strategic contribution to the quantitative investment firm, and the production/runtime/threshold/signal/order/portfolio/NAV/exposure changes that remain unauthorized.

## Active campaign

**Campaign:** Campaign #45 — Historical Regime State and Transition Discovery

**Classification:** Research primary; deterministic historical alpha discovery and falsification

**Status:** SPECIFICATION FROZEN — specification-only transition complete; implementation, predictive-result generation, and artifact publication remain unauthorized pending estimator and preflight handoff review

**Working branch:** `agent/campaign-45-historical-regime-transitions`

**Repository:** `IteraDynamics/ID_test`

**Governing specification:** `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY.md`

**Specification freeze commit:** `7d9cf4bb1abb556e99ffce21127cf98379dc968e`

## Immediate objective

Freeze and test a finite inventory of anchor-local historical regime states and transitions for incremental association with forward BTC outcomes, using deterministic event-family or chronologically separated independence controls and simple BTC price-state baselines.

Campaign #45 tests historical information contained in regime states and transitions. It does not redesign, replace, or alter the existing regime detector.

## Exact research question

Across the governed historical BTC regime artifacts, do pre-registered anchor-local regime states or transitions show directionally stable, independently supported, out-of-sample association with forward BTC outcomes after comparison with simple BTC price-state baselines?

## Strategic contribution

Campaign #45 investigates the highest-priority research surface selected by Campaign #44. It tests whether the evolution of governed market-state labels contains incremental information beyond simple price state, while preserving a finite falsification path and strict independence controls.

A successful research result would remain a preliminary historical association. It would not authorize deployment, runtime integration, portfolio construction, or strategy changes.

## Authorization

**Decision:** GO for the specification-only Campaign #45 transition.

The user explicitly authorized proceeding on July 28, 2026 after reviewing the distinction between existing regime detection and historical state-transition research.

Authorized now:

- create and freeze the Campaign #45 governing specification;
- update this campaign board;
- inspect existing governed documentation, schemas, code, manifests, and canonical artifacts to prepare an exact implementation handoff;
- resolve source identity, field timing, estimator, multiplicity control, representative-anchor rule, and preflight requirements without inspecting new predictive results.

Not yet authorized:

- implementation code;
- predictive-return generation or inspection;
- canonical result generation;
- artifact publication;
- tuning after result inspection;
- model training or replacement;
- any production or runtime behavior change.

## Relationship to existing regime detection

The existing regime workflow identifies and labels governed historical market conditions and episodes.

Campaign #45 treats eligible anchor-local labels as immutable research inputs and asks whether the current state, prior state, ordered transition, state age, or transition spacing contains stable historical association with later BTC outcomes.

Campaign #45 must not:

- alter regime classification logic;
- create a new live regime;
- alter any threshold;
- change strategy selection;
- use recovery outcome or other post-anchor information as a predictor;
- represent a historical association as a trading signal.

## Frozen Campaign #45 framework

The governing specification freezes:

- predictor classes P-001 through P-005;
- prohibited leakage-prone predictors;
- simple BTC price-state controls;
- primary 24-hour, 72-hour, and 168-hour horizons;
- event-family or chronologically purged independence controls;
- expanding chronological evaluation;
- minimum independent-support gates;
- null and insufficient-support visibility;
- finite falsification rules;
- deterministic canonical outputs;
- replay and LF-only requirements.

The exact statistical estimator, multiplicity-control method, categorical control representation, representative-family anchor rule, source manifest, and preflight contract must be frozen in a separate implementation handoff before predictive-result generation can be authorized.

## Governing constraints

All work must remain:

- deterministic;
- replay-safe;
- research-only;
- observation-only;
- fail-closed;
- leakage-safe;
- independent of production runtime state mutation.

Campaign #45 does not authorize:

- production runtime integration;
- model training, replacement, or recalibration;
- threshold, signal, intent, or strategy changes;
- orders or execution;
- portfolio construction;
- NAV or exposure changes;
- dashboard changes;
- transaction-cost, capacity, or deployable-alpha claims;
- arbitrary feature combinations or post-result transformations;
- learned transition classes or clustering;
- promotion of any historical association into a live rule.

## Authorized file surfaces

During the current specification and handoff phase, Campaign #45 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY.md`;
- one new implementation handoff under `docs/research/`.

After a separate implementation GO, the board may authorize:

- a new observation-only implementation module under `research/ml/validation/`;
- a new Campaign #45 runner under `scripts/`;
- focused Campaign #45 tests under `tests/`;
- `artifacts/historical_regime_transitions/**`.

Any additional file surface requires an explicit board transition.

## Acceptance gates

1. The governing specification predates predictive-result inspection. **Passed: frozen in commit `7d9cf4bb1abb556e99ffce21127cf98379dc968e`.**
2. Existing regime detection remains unchanged. **Passed for the specification transition; no runtime or classifier files changed.**
3. Exact source identities, hashes, schemas, and timestamp semantics are frozen before implementation. **Pending implementation handoff.**
4. Predictor fields are proven anchor-local or excluded. **Pending preflight contract and implementation.**
5. Recovery-dependent and post-anchor fields are prohibited as predictors. **Passed in specification.**
6. Exact estimator, multiplicity control, representative-anchor rule, and categorical control representation predate result inspection. **Pending implementation handoff.**
7. Candidate inventory, chronological folds, and purge rules are deterministic. **Specified; pending implementation.**
8. Overlapping episodes cannot inflate independent support. **Specified; pending focused tests.**
9. Simple BTC price-state controls are implemented exactly as frozen. **Pending implementation.**
10. Focused tests cover leakage, duplicate anchors, support gates, fold purging, null visibility, deterministic ordering, and replay. **Pending.**
11. Governed preflight passes before predictive generation. **Pending.**
12. Two governed runs produce byte-identical canonical outputs. **Pending.**
13. Canonical text outputs are LF-only. **Pending.**
14. Full repository suite passes with no new failures. **Pending.**
15. Scope review finds no production, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes. **Passed for specification transition; must remain true.**

## Immediate sequence

1. Freeze the Campaign #45 governing specification. **Completed.**
2. Record the specification-only transition on the authoritative board. **Completed.**
3. Prepare an exact implementation handoff covering source hashes and schemas, timestamp semantics, estimator, multiplicity control, categorical controls, representative anchors, canonical schemas, and preflight behavior. **Authorized next.**
4. Review the handoff and record a separate implementation GO. **Pending.**
5. Implement observation-only research code and focused tests. **Unauthorized until step 4.**
6. Run governed preflight. **Unauthorized until step 4.**
7. Generate and inspect predictive results only after all frozen pre-result gates pass. **Unauthorized until step 4.**

## Campaign #44 closure

Campaign #44 — Alpha Surface Discovery and Research Prioritization is complete on branch `agent/campaign-44-alpha-surface-discovery`.

Completion evidence:

- specification frozen before ranking inspection: `7ebf68f81c731a9486e161ecb99571cb17027ee9`;
- focused suite: `10 passed`, `0 failed`;
- governed preflight passed;
- 24 cited repository sources validated;
- 8 inventory surfaces validated;
- canonical generation passed;
- replay verification passed with digest `612a340340d60223579306d7a87fc8715c03f46c1ffa36219e882fa21cbbd011`;
- canonical staged repository blobs verified LF-only;
- full repository suite: `449 passed`, `0 failed`;
- canonical artifact publication commit: `a9bf487`;
- branch pushed to origin on July 28, 2026;
- no new predictive returns were generated or inspected;
- no production, runtime, model-training, threshold, signal, strategy, order, portfolio, NAV, exposure, execution, or dashboard changes were made.

Campaign #44 ranked four research surfaces:

1. S-002 — Historical regime state and transition structure: 29;
2. S-003 — Historical event persistence, clustering, duration, and spacing: 27;
3. S-008 — Simple BTC price-state baselines: 26;
4. S-001 — Registered Core v1 collapse structure candidate A-001: 26.

The canonical roadmap selected S-002 as the finite next campaign.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains a preliminary collapse-structure association requiring independent falsification.

- Surface: Core v1 collapse structure.
- Primary descriptor pattern: `VOLATILITY_NEUTRAL` and `LOW_DISPLACEMENT_COLLAPSE`.
- Primary horizon: 24 hours.
- Secondary nested pattern: `SEVERE_COLLAPSE` and `SEVERE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`.
- Secondary horizon: 72 hours.
- Constraint: the severe subset contains only five independent event families and must not be represented as an independent deployable signal.

Campaign #45 does not revise, promote, or retest Candidate A-001 unless an explicitly frozen candidate in the Campaign #45 inventory independently includes the same anchor-local information under the new specification.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #45 authorization.
