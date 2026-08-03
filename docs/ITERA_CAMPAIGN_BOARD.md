# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #51 — Conditional Directional Value of Supported BTC Movement States

**Status:** PLANNING OPEN — source-and-variable feasibility inventory authorized; implementation, forward outcomes, model fitting, holdout access, economic testing, paper trading, and runtime/strategy work prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Determine whether BTC volatility and drawdown states already supported by Campaign #48 identify conditions under which a separately defined, pre-existing directional variable has materially different forward directional value.

Campaign #51 does not ask volatility or drawdown to predict direction unconditionally. It asks whether supported movement states condition the value of independently defined directional information.

## Governed antecedents

### Campaign #48

Campaign #48 established 15 supported research associations under its frozen BTC price-state design.

All supported associations were concentrated in:

- recent realized volatility and future absolute return;
- recent realized volatility and future realized volatility;
- deeper drawdown from the trailing 168-hour high and higher future realized volatility.

No directional-return candidate was supported.

Campaign #48 closure:

- `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

Campaign #48 canonical publication:

- `fd7ee01`

### Campaign #50

Campaign #50 is permanently closed as a valid governed negative result.

Final closure record:

- `docs/research/CAMPAIGN_50_FINAL_CLOSURE.md`
- commit `abc38f2cba5cb28603632c4302845e490cb9f4c1`

Final result:

- 24 frozen equity-breadth candidates;
- 16 `DISCOVERY_NOT_SUPPORTED`;
- 8 `INSUFFICIENT_EVENT_SUPPORT`;
- 0 discovery-supported;
- 0 validation-supported;
- empty shortlist;
- 2025 holdout untouched;
- all six canonical artifacts byte-identical across two governed replays.

Campaign #50 may not be reopened by post-outcome method changes.

## Campaign #51 planning charter

The governing planning document is:

- `docs/research/CAMPAIGN_51_CONDITIONAL_DIRECTIONAL_VALUE_PLANNING_CHARTER.md`
- commit `59359493787dcac855063debbda8a76895a55378`

The charter freezes the planning purpose and stage boundaries but does not select or authorize a final candidate family.

## Planning scope

Initial directional-variable inventory may inspect only variables that are:

- already present in the repository or mechanically derivable from a governed price source;
- defined independently of Campaign #51 outcomes;
- interpretable before testing;
- chronologically and leakage-safe;
- available with enough coverage for development, validation, and untouched confirmation;
- research-only and disconnected from runtime behavior.

Possible inventory categories include:

- recent signed return or momentum state;
- long-horizon trend state;
- price-location or breakout state;
- existing deterministic research-only directional intent or score.

This is inventory scope, not authorization to test every category.

Initial movement-state inventory is limited to Campaign #48-supported families:

- trailing 24-hour realized volatility;
- trailing 168-hour realized volatility;
- drawdown from the trailing 168-hour high.

No threshold optimization is authorized.

## Candidate-budget constraint

The later frozen candidate family should be deliberately small:

- preferred range: 6 to 12 candidates;
- planning ceiling: 18 candidates unless a separate pre-outcome board decision justifies more.

Candidate count must be frozen before any outcome generation.

## Required next deliverable

A source-and-variable feasibility inventory that generates no Campaign #51 forward outcomes.

It must document:

- exact candidate directional variables already available;
- exact formulas and source lineage;
- compatible Campaign #48 movement-state variables;
- exact common date coverage;
- source hashes, schemas, cadence, and missing-data constraints;
- calendar-only maximum sample counts by proposed horizon and partition;
- leakage, duplication, and dependency concerns;
- a recommended narrow family for later board selection.

It must not calculate:

- forward returns;
- conditional directional accuracy;
- coefficients;
- p-values;
- rankings;
- support outcomes;
- economic performance.

## Current authorization

**Decision:** GO for planning and observation-only feasibility inventory only.

Authorized now:

- inspect repository research variables and source lineage;
- inspect Campaign #48 definitions and governed artifacts;
- inventory directional variables without generating Campaign #51 outcomes;
- validate source hashes, schemas, timestamp ordering, cadence, and coverage;
- compute calendar-only sample feasibility without loading forward outcomes;
- draft a family-selection memo based only on economic rationale and non-outcome feasibility;
- update this board with planning evidence.

Not authorized:

- implementation of a Campaign #51 analytical runner;
- generation of Campaign #51 forward outcomes;
- fitting models or computing coefficients, p-values, rankings, or support decisions;
- selecting variables based on observed forward performance;
- loading an untouched holdout analytically;
- economic-value testing or Core v1 comparison;
- paper trading;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Mandatory stage separation

1. Planning charter — **completed**.
2. Source-and-variable feasibility inventory — **authorized next**.
3. Hypothesis-family selection — **pending**.
4. Frozen statistical specification — **not authorized yet**.
5. Implementation and synthetic tests — **not authorized**.
6. Development and validation execution — **not authorized**.
7. Untouched historical confirmation — **not authorized**.
8. Economic testing — **not authorized**.
9. Forward paper trading — **not authorized**.
10. Limited-live-capital review — **not authorized**.

Passing one stage does not authorize the next.

## Immediate sequence

1. Inventory existing deterministic directional variables and their exact formulas.
2. Map them to governed source files and date coverage.
3. Reconcile them with Campaign #48-supported movement-state definitions.
4. Produce calendar-only feasibility and leakage analysis.
5. Recommend one narrow candidate family without examining forward outcomes.
6. Return to the board for family-selection authorization.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
