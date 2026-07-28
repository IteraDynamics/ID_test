# Campaign #44 — Alpha Surface Discovery and Research Prioritization

## Status

Specification frozen for deterministic, observation-only implementation planning.

## Immediate objective

Construct Itera Dynamics' first governed Alpha Surface Map: a deterministic inventory and prioritization of existing research surfaces that identifies where the firm should allocate its next research campaigns to maximize the probability of discovering economically meaningful, independently testable alpha.

Campaign #44 does not attempt to prove or deploy any trading signal. It determines what should be researched next and why.

## Strategic contribution

Itera Dynamics is building an institutional-grade quantitative investment firm. The firm therefore needs a repeatable process for allocating research effort across candidate alpha surfaces rather than exhaustively extending whichever result was most recently produced.

Campaign #44 converts the existing repository, governed artifacts, and registered findings into:

1. an explicit alpha-surface inventory;
2. a deterministic Research Expected Value framework;
3. a ranked research roadmap;
4. frozen candidate briefs suitable for subsequent discovery or falsification campaigns.

## Exact research question

Across Itera's currently governed, anchor-available, leakage-safe data and research artifacts, which alpha surfaces offer the highest expected value for the next finite research campaign when judged by independent support, economic plausibility, uniqueness, falsifiability, data readiness, implementation cost, and potential portfolio usefulness?

## Governing principles

All Campaign #44 work must remain:

- deterministic;
- replay-safe;
- research-only;
- observation-only;
- fail-closed;
- explicit about unavailable or insufficient evidence;
- free of post-result score changes.

The campaign must not search arbitrary feature combinations or inspect new predictive returns while constructing the inventory and prioritization methodology.

## Scope

### In scope

Campaign #44 may inspect repository-tracked documentation, schemas, tests, research code, manifests, and canonical artifacts to identify existing research surfaces and their metadata.

Eligible surface classes include, when repository evidence exists and the information is anchor-available:

- market and price-derived features;
- regime classifications and transitions;
- jump-risk and collapse descriptors;
- model confidence, calibration, disagreement, and consensus outputs;
- cross-origin signal agreement and divergence;
- event structure, persistence, clustering, duration, and spacing;
- historical robustness and stability evidence;
- candidate findings already registered by completed campaigns.

Campaign #44 may classify a surface as unavailable, leakage-prone, insufficiently governed, redundant, or not research-ready.

### Out of scope

Campaign #44 may not:

- generate or inspect new predictive-outcome results;
- create arbitrary transformations or interactions;
- tune a scoring method after seeing rankings;
- train, replace, or recalibrate a model;
- alter production runtime behavior;
- change thresholds, signals, intents, strategies, orders, execution, portfolio construction, NAV, or exposure;
- claim deployable alpha, expected trading profit, capacity, or transaction-cost viability;
- authorize cross-asset production work.

## Campaign #43 registration

Campaign #43-R1 is registered as an existing preliminary alpha candidate rather than an automatic next campaign.

### Registered Candidate A-001

- Surface: Core v1 collapse structure.
- Primary descriptor pattern: `VOLATILITY_NEUTRAL` and `LOW_DISPLACEMENT_COLLAPSE`.
- Primary horizon: 24 hours.
- Secondary nested pattern: `SEVERE_COLLAPSE` and `SEVERE_COLLAPSE__LOW_DISPLACEMENT_COLLAPSE__VOLATILITY_NEUTRAL`.
- Secondary horizon: 72 hours.
- Status: preliminary supported association requiring independent falsification.
- Constraint: the severe subset has only five independent event families and must not be represented as an independent deployable signal.

## Alpha Surface Inventory

Each inventory row must contain only evidence available before any new predictive result inspection.

Required fields:

- `surface_id`;
- `surface_name`;
- `surface_class`;
- `repository_sources`;
- `governance_state`;
- `anchor_availability`;
- `leakage_state`;
- `observation_unit`;
- `independence_unit`;
- `available_observation_count`;
- `available_independence_count`;
- `historical_span_start`;
- `historical_span_end`;
- `asset_scope`;
- `candidate_horizons`;
- `existing_evidence_state`;
- `known_overlap_or_redundancy`;
- `data_readiness_state`;
- `estimated_implementation_complexity`;
- `falsification_path`;
- `portfolio_relevance_hypothesis`;
- `notes`.

Unknown values must remain explicitly unknown. The implementation must not infer missing counts, dates, or governance status from filenames alone.

## Research Expected Value framework

Campaign #44 ranks research programs, not trading signals.

### Frozen dimensions

Each eligible surface receives an integer score from `0` through `4` for each dimension using rules frozen before final ranking inspection:

1. **Independent support potential** — expected number and diversity of non-overlapping observations available for a future test.
2. **Data readiness** — identity, schema, temporal coverage, and anchor availability of governed inputs.
3. **Economic plausibility** — existence of a coherent mechanism connecting the surface to forward returns or risk, without using observed predictive performance as proof.
4. **Uniqueness** — degree to which the surface may contribute information not already represented by simpler price or existing Itera features.
5. **Falsifiability** — ability to define a finite, pre-registered test that can clearly reject the hypothesis.
6. **Portfolio relevance** — plausible future contribution through frequency, diversification, horizon, or regime specificity; this is a research hypothesis, not a performance claim.
7. **Implementation efficiency** — expected engineering and research burden for a governed finite campaign.
8. **Governance readiness** — ability to freeze sources, candidates, anchors, outcomes, and acceptance gates before result inspection.

### Fail-closed penalties

A surface is not rankable and must be assigned an explicit non-rankable state if any of the following applies:

- anchor availability cannot be established;
- predictor leakage is known or unresolved;
- source identity or schema cannot be governed;
- no finite falsification test can be stated;
- the surface requires unauthorized runtime or production changes merely to be researched;
- repository evidence is insufficient to characterize the surface without speculation.

### Ranking tuple

Rankable surfaces are ordered deterministically by:

1. descending total frozen-dimension score;
2. descending independent-support-potential score;
3. descending uniqueness score;
4. descending falsifiability score;
5. descending portfolio-relevance score;
6. ascending implementation-complexity score;
7. ascending `surface_id`.

Scores are research-priority aids only. They are not probabilities of alpha and must not be converted into expected returns.

## Required outputs

Under `artifacts/alpha_surface_discovery/`:

- `alpha_surface_inventory.json`;
- `alpha_surface_inventory.csv`;
- `alpha_research_priorities.json`;
- `alpha_research_priorities.csv`;
- `alpha_research_roadmap.md`;
- `alpha_surface_discovery_manifest.json`.

## Acceptance evidence

Campaign #44 is accepted only if:

1. the specification and scoring rules are committed before final inventory ranking inspection;
2. every inventory row cites concrete repository evidence;
3. anchor availability, leakage state, governance state, and missing evidence remain explicit;
4. non-rankable surfaces remain visible with fail-closed reasons;
5. Campaign #43 A-001 is registered without promotion or score inflation from duplicated descriptor rows;
6. scoring and ranking are deterministic and covered by focused tests;
7. two governed runs produce byte-identical canonical outputs;
8. canonical text outputs are LF-only;
9. the full repository test suite has no new failures;
10. the roadmap recommends a finite next campaign with an exact objective, falsification path, data requirements, and authorization boundary;
11. no production, runtime, threshold, signal, strategy, order, execution, portfolio, NAV, exposure, model-training, or dashboard behavior changes occur.

## Authorized initial file surfaces

The initial implementation phase may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/ALPHA_SURFACE_DISCOVERY_AND_PRIORITIZATION.md`;
- a new observation-only inventory module under `research/ml/validation/`;
- a new Campaign #44 runner under `scripts/`;
- focused Campaign #44 tests under `tests/`;
- `artifacts/alpha_surface_discovery/**`.

Any additional file surface requires an explicit board transition.

## Authorization boundary

This specification authorizes deterministic implementation of the inventory, frozen Research Expected Value scoring, canonical serialization, focused tests, governed preflight, and replay verification only after the campaign board records the transition.

It does not authorize new predictive-return discovery, alpha validation, model training, runtime integration, threshold or signal changes, strategy changes, orders, execution, portfolio construction, NAV changes, exposure changes, or production deployment.
