# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`: Itera Dynamics is building an institutional-grade quantitative investment firm. That thesis is directional context only and does not modify any active campaign authorization.

Beginning with Campaign #44, every campaign proposal must state its immediate objective, acceptance evidence, strategic contribution to the quantitative investment firm, and the production/runtime/threshold/signal/order/portfolio/NAV/exposure changes that remain unauthorized.

## Active campaign

**Campaign:** Campaign #44 — Alpha Surface Discovery and Research Prioritization

**Classification:** Research primary; deterministic alpha-surface inventory and research-capital allocation

**Status:** SPECIFICATION FROZEN — observation-only inventory, scoring implementation, tests, governed preflight, canonical serialization, and two-run replay validation authorized; new predictive-return discovery is not authorized

**Working branch:** `agent/campaign-44-alpha-surface-discovery`

**Repository:** `IteraDynamics/ID_test`

**Governing specification:** `docs/research/ALPHA_SURFACE_DISCOVERY_AND_PRIORITIZATION.md`

**Specification freeze commit:** `7ebf68f81c731a9486e161ecb99571cb17027ee9`

## Immediate objective

Construct Itera Dynamics' first governed Alpha Surface Map: a deterministic inventory and prioritization of existing research surfaces that identifies where the firm should allocate its next finite research campaigns to maximize the probability of discovering economically meaningful, independently testable alpha.

Campaign #44 ranks research opportunities, not trading signals. It must not generate or inspect new predictive returns.

## Exact research question

Across Itera's currently governed, anchor-available, leakage-safe data and research artifacts, which alpha surfaces offer the highest expected value for the next finite research campaign when judged by independent support, economic plausibility, uniqueness, falsifiability, data readiness, implementation cost, and potential portfolio usefulness?

## Strategic contribution

Campaign #44 creates a repeatable process for allocating research effort across the firm's available alpha surfaces instead of allowing the most recent result to monopolize subsequent campaigns.

The required strategic outputs are:

1. an explicit alpha-surface inventory;
2. a deterministic Research Expected Value framework;
3. a ranked research roadmap;
4. finite candidate briefs suitable for later discovery or falsification campaigns.

## Authorization

**Decision:** GO for deterministic implementation of the frozen Campaign #44 inventory and Research Expected Value scoring framework, canonical serialization, focused tests, governed preflight, and two-run replay validation.

The user explicitly authorized Campaign #44 on July 28, 2026 after directing that Itera move fund-directionally toward broad alpha discovery and research prioritization rather than automatically extending the narrow Campaign #43 subset.

The campaign may inspect repository-tracked documentation, schemas, research code, tests, manifests, and canonical artifacts to identify existing research surfaces and their pre-existing metadata.

It may not inspect or generate new predictive-return results, tune scores after ranking inspection, train or replace a model, or alter production behavior.

## Governing constraints

All work must remain deterministic, replay-safe, research-only, observation-only, and fail-closed.

Campaign #44 does not authorize:

- production runtime integration;
- model training, replacement, or recalibration;
- threshold, signal, intent, or strategy changes;
- orders or execution;
- portfolio construction;
- NAV or exposure changes;
- dashboard changes;
- transaction-cost, capacity, or deployable-alpha claims;
- arbitrary feature combinations or post-result transformations;
- new predictive-outcome discovery during inventory construction.

## Campaign #43-R1 closure and registration

Campaign #43-R1 — Core v1 Historical Alpha Discovery is complete on branch `agent/campaign-43-historical-alpha-discovery-r1`.

Completion evidence:

- focused Campaign #43 tests passed;
- full repository suite passed with `439 passed`, `0 failed`;
- governed preflight passed;
- canonical outputs generated;
- two governed runs produced byte-identical artifacts;
- replay digest: `babea2abadf6617b0fd94337c9be07cf...`;
- canonical text outputs verified LF-only;
- publication commit: `8bc238b`;
- branch pushed to origin on July 28, 2026.

Campaign #43's result is registered as a preliminary candidate, not promoted to production and not automatically selected as the next dedicated campaign.

### Registered Candidate A-001

- Surface: Core v1 collapse structure.
- Primary descriptor pattern: `VOLATILITY_NEUTRAL` and `LOW_DISPLACEMENT_COLLAPSE`.
- Primary horizon: 24 hours.
- Secondary nested pattern: `SEVERE_COLLAPSE` and `SEVERE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`.
- Secondary horizon: 72 hours.
- Status: preliminary supported association requiring independent falsification.
- Constraint: the severe subset contains only five independent event families and must not be represented as an independent deployable signal.

Campaign #43-R1 remains governed exactly by:

- `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md`;
- `docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY_R1.md`;
- its frozen sources, candidates, anchors, outcomes, horizons, folds, support rules, ranking, outputs, and authorization boundary.

No Campaign #43 result may be revised in place after inspection.

## Frozen Campaign #44 framework

### Eligible surface classes

When concrete repository evidence exists and predictor information is anchor-available, the inventory may include:

- market and price-derived features;
- regime classifications and transitions;
- jump-risk and collapse descriptors;
- model confidence, calibration, disagreement, and consensus outputs;
- cross-origin signal agreement and divergence;
- event structure, persistence, clustering, duration, and spacing;
- historical robustness and stability evidence;
- candidate findings already registered by completed campaigns.

### Research Expected Value dimensions

Each rankable surface receives a frozen integer score from `0` through `4` for:

1. independent support potential;
2. data readiness;
3. economic plausibility;
4. uniqueness;
5. falsifiability;
6. portfolio relevance;
7. implementation efficiency;
8. governance readiness.

The exact scoring rules and deterministic ranking tuple are governed by `docs/research/ALPHA_SURFACE_DISCOVERY_AND_PRIORITIZATION.md`.

Scores rank research programs only. They are not probabilities of alpha, expected returns, or deployment recommendations.

### Fail-closed non-rankable states

A surface remains visible but non-rankable when:

- anchor availability cannot be established;
- predictor leakage is known or unresolved;
- source identity or schema cannot be governed;
- no finite falsification test can be stated;
- research would require unauthorized production behavior changes;
- repository evidence is insufficient without speculation.

Unknown values must remain explicitly unknown. Counts, dates, governance status, or schema must not be inferred from filenames alone.

## Authorized file surfaces

The initial Campaign #44 implementation may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/ALPHA_SURFACE_DISCOVERY_AND_PRIORITIZATION.md`;
- a new observation-only inventory module under `research/ml/validation/`;
- a new Campaign #44 runner under `scripts/`;
- focused Campaign #44 tests under `tests/`;
- `artifacts/alpha_surface_discovery/**`.

Any additional file surface requires an explicit board transition.

## Planned canonical outputs

Under `artifacts/alpha_surface_discovery/`:

- `alpha_surface_inventory.json`;
- `alpha_surface_inventory.csv`;
- `alpha_research_priorities.json`;
- `alpha_research_priorities.csv`;
- `alpha_research_roadmap.md`;
- `alpha_surface_discovery_manifest.json`.

## Acceptance gates

1. Campaign #44 specification and scoring rules predate final ranking inspection. **Passed: specification frozen in commit `7ebf68f81c731a9486e161ecb99571cb17027ee9`.**
2. Every inventory row cites concrete repository evidence. **Pending implementation.**
3. Anchor availability, leakage state, governance state, and missing evidence remain explicit. **Pending implementation.**
4. Non-rankable surfaces remain visible with fail-closed reasons. **Pending implementation.**
5. Campaign #43 A-001 is registered without promotion or score inflation from duplicated descriptor rows. **Passed in board and specification; implementation test pending.**
6. Scoring and ranking are deterministic and covered by focused tests. **Pending implementation.**
7. Governed preflight validates all cited repository inputs before canonical generation. **Pending implementation.**
8. Two governed runs produce byte-identical canonical outputs. **Pending.**
9. Canonical text outputs are LF-only. **Pending.**
10. Full repository suite passes with no new failures. **Pending.**
11. The roadmap recommends a finite next campaign with an exact objective, falsification path, data requirements, and authorization boundary. **Pending.**
12. Scope review finds no production, runtime, threshold, signal, strategy, order, execution, portfolio, NAV, exposure, model-training, or dashboard changes. **Must remain true.**
13. No new predictive returns are generated or inspected during Campaign #44. **Must remain true.**

## Immediate implementation sequence

1. inventory concrete governed research surfaces from repository evidence;
2. encode frozen schemas and fail-closed validation;
3. implement deterministic Research Expected Value scoring and ranking;
4. add focused tests, including duplicated-evidence and non-rankable cases;
5. run governed preflight;
6. generate canonical outputs twice and verify replay identity;
7. inspect the resulting roadmap only after deterministic generation is complete.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #44 authorization.
