# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`: Itera Dynamics is building an institutional-grade quantitative investment firm. That thesis is directional context only and does not modify any active campaign authorization.

Beginning with Campaign #44, every campaign proposal must state its immediate objective, acceptance evidence, strategic contribution to the quantitative investment firm, and the production/runtime/threshold/signal/order/portfolio/NAV/exposure changes that remain unauthorized.

## Active campaign

**Campaign:** Campaign #45 — Historical Regime State and Transition Discovery

**Classification:** Research primary; deterministic historical alpha discovery and falsification

**Status:** PREFLIGHT HANDOFF NO-GO — current governed source set provides only 14 independent event families against the frozen minimum of 20; implementation, predictive-result generation, canonical result generation, and artifact publication remain unauthorized

**Working branch:** `agent/campaign-45-historical-regime-transitions`

**Repository:** `IteraDynamics/ID_test`

**Governing specification:** `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY.md`

**Specification freeze commit:** `7d9cf4bb1abb556e99ffce21127cf98379dc968e`

**Implementation handoff:** `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY_IMPLEMENTATION_HANDOFF.md`

**Handoff commit:** `709a40b95a1fff9954eb15e3f7944499e71dbbb8`

## Immediate objective

Determine whether Campaign #45 can be supplied with at least 20 genuinely independent, anchor-local historical regime observations without weakening the frozen support gate, counting overlapping episodes as independent, introducing leakage, or changing production behavior.

The original research objective remains to test a finite inventory of anchor-local historical regime states and transitions for incremental association with forward BTC outcomes. Predictive testing cannot begin until the independent-support feasibility issue is resolved through a separate board transition.

## Exact research question

Across a sufficiently supported governed historical BTC regime population, do pre-registered anchor-local regime states or transitions show directionally stable, independently supported, out-of-sample association with forward BTC outcomes after comparison with simple BTC price-state baselines?

## Strategic contribution

Campaign #45 investigates the highest-priority research surface selected by Campaign #44. The pre-result handoff has already produced useful falsification evidence: the collapse-only episode population is too small at the independent-family level for the frozen confirmatory design.

This prevents Itera from manufacturing statistical support by treating 122 overlapping rolling-window episodes as 122 independent events when they reconcile into only 14 governed event families.

## Authorization

**Decision:** NO-GO for predictive implementation against the current governed source set.

The user explicitly authorized proceeding on July 28, 2026. Under that authorization, the exact implementation handoff was prepared without inspecting predictive outcomes. The handoff found that the current source set cannot meet the frozen minimum independent-support gate.

Authorized now:

- inspect existing governed documentation, schemas, code, manifests, and canonical artifacts to determine whether a longer or full anchor-local historical regime sequence already exists;
- prepare a proposal for an extended governed source or a full-state-sequence population;
- verify source identity, timestamp semantics, anchor locality, continuity, and independent-support feasibility without constructing forward outcomes;
- close Campaign #45 as infeasible under current evidence if no compliant source exists;
- propose advancing to the next Campaign #44 priority.

Not authorized:

- implementation code for predictive testing;
- predictive-return generation or inspection;
- canonical result generation;
- artifact publication;
- lowering the minimum support gate;
- counting overlapping episodes within a family as independent;
- estimator selection based on current outcomes;
- model training or replacement;
- any production or runtime behavior change.

## Pre-result support-feasibility finding

Frozen minimum support gate:

- at least 20 independent event families or chronologically purged observations overall;
- at least 5 independent observations in each required chronological evaluation fold.

Current governed source evidence:

- historical episode rows: 122;
- unique event-family membership rows: 122;
- independent event families: 14;
- maximum independent support available from the current collapse-episode population: 14;
- minimum required: 20;
- deficit: 6;
- rankable candidates possible under the current source set: 0.

The chronologically purged fallback cannot be used to split governed event families. When family identity applies, multiple overlapping member episodes remain one independent observation.

No predictive outcomes, candidate coefficients, p-values, rankings, or canonical result artifacts were generated or inspected.

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

The governing specification remains frozen and includes:

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

No frozen gate or research definition may be weakened in place to overcome the support failure.

## Resolved source boundary

The implementation handoff records exact identities for:

- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`;
- `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`;
- `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`;
- `artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json`;
- `artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv`;
- externally provisioned `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`.

The BTC source remains exact-match only. No interpolation, filling, resampling, nearest-row matching, as-of matching, or alternate price substitution is authorized.

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

During the current feasibility-resolution phase, Campaign #45 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY.md`;
- `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY_IMPLEMENTATION_HANDOFF.md`;
- one new source-feasibility proposal or closure document under `docs/research/`.

No observation module, runner, test, or result-artifact surface is authorized until a separate implementation GO is recorded.

Any additional file surface requires an explicit board transition.

## Acceptance gates

1. Governing specification predates predictive-result inspection. **Passed.**
2. Existing regime detection remains unchanged. **Passed to date.**
3. Exact current source identities, hashes, schemas, and timestamp semantics are frozen. **Passed in implementation handoff.**
4. Predictor fields are proven anchor-local or excluded. **Contract frozen; implementation pending.**
5. Recovery-dependent and post-anchor fields are prohibited as predictors. **Passed in specification and handoff.**
6. Exact estimator and multiplicity method predate result inspection. **Not activated; blocked by support feasibility.**
7. Candidate inventory, chronological folds, and purge rules are deterministic. **Specified; implementation blocked.**
8. Overlapping episodes cannot inflate independent support. **Passed in handoff decision.**
9. Minimum overall independent support is at least 20. **Failed for current source set: 14.**
10. At least 5 independent observations exist in each required evaluation fold. **Not evaluated because overall support already fails.**
11. Governed preflight passes before predictive generation. **Failed closed at support-feasibility stage.**
12. Scope review finds no production, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes. **Passed to date; must remain true.**

## Immediate sequence

1. Freeze the Campaign #45 governing specification. **Completed.**
2. Record the specification-only transition. **Completed.**
3. Prepare the exact implementation handoff. **Completed.**
4. Run pre-result independent-support feasibility review. **Completed: NO-GO, 14 available versus 20 required.**
5. Determine whether an already governed full historical state sequence can provide at least 20 anchor-local independent observations. **Authorized next.**
6. If not, choose between an explicitly governed source-extension campaign or Campaign #45 closure. **Pending.**
7. Record a separate implementation GO only after sufficient support, exact estimator, multiplicity control, folds, and preflight contract are frozen. **Pending.**
8. Predictive generation and inspection remain unauthorized until step 7. **Blocked.**

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
- no new predictive returns were generated or inspected;
- no production, runtime, model-training, threshold, signal, strategy, order, portfolio, NAV, exposure, execution, or dashboard changes were made.

Campaign #44 ranked four research surfaces:

1. S-002 — Historical regime state and transition structure: 29;
2. S-003 — Historical event persistence, clustering, duration, and spacing: 27;
3. S-008 — Simple BTC price-state baselines: 26;
4. S-001 — Registered Core v1 collapse structure candidate A-001: 26.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains a preliminary collapse-structure association requiring independent falsification.

- Surface: Core v1 collapse structure.
- Primary descriptor pattern: `VOLATILITY_NEUTRAL` and `LOW_DISPLACEMENT_COLLAPSE`.
- Primary horizon: 24 hours.
- Secondary nested pattern: `SEVERE_COLLAPSE` and `SEVERE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`.
- Secondary horizon: 72 hours.
- Constraint: the severe subset contains only five independent event families and must not be represented as an independent deployable signal.

Campaign #45 does not revise, promote, or retest Candidate A-001 unless a separately frozen sufficient-support population independently includes the same anchor-local information.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #45 authorization.
