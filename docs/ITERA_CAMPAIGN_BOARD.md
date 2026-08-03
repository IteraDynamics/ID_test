# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** PLANNING OPEN — planning charter committed; reference-artifact and intervention feasibility inventory is the next authorized deliverable. Counterfactual generation, NAV reconstruction, performance comparison, model fitting, execution, holdout access, and runtime/strategy changes remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Determine whether canonical Core v1 derives material value from the correct chronological alignment of its state-conditioned decisions, beyond what can be explained by average exposures, sleeve composition, and activity profile.

Campaign #52 is an architecture-falsification campaign. It is not another standalone directional-feature search and it does not reopen Campaign #51.

## Governed antecedents

### Campaign #48

Campaign #48 retained supported associations involving BTC volatility, drawdown, and future movement magnitude or volatility.

### Campaign #50

Campaign #50 closed as a governed negative directional result with an empty shortlist and untouched 2025 holdout.

### Campaign #51

Campaign #51 closed as a governed negative result:

- final closure: `docs/research/CAMPAIGN_51_FINAL_CLOSURE.md`;
- closure commit: `f9858cf8ceacb669f69d569250410ae289c6126d`;
- 12 of 12 candidates: `DISCOVERY_NOT_SUPPORTED`;
- validation eligible: `0`;
- shortlist: empty;
- 2025 analytical values: untouched;
- canonical replay artifacts: byte-identical.

Campaign #51 may not be reopened or reinterpreted through post-outcome method changes.

## Campaign #52 planning record

- planning charter: `docs/research/CAMPAIGN_52_CORE_V1_CHRONOLOGICAL_STATE_VALUE_PLANNING_CHARTER.md`;
- charter commit: `8ad9f3aae3dc4b36010ef8f723ae1c88bbf7db9d`.

## Planning reference

The current planning reference is the blessed Core v1 candidate documented in:

- `research/trade_idea_radar/CORE_V1_BASELINE_MANIFEST.md`;
- allocation: trend `0.40`, equity `0.35`, gold `0.15`, hedge `0.10`, mean reversion `0.00`;
- defining architecture: explicit BTC macro-state ownership across crypto trend sleeves.

This is not yet a frozen Campaign #52 execution reference. Exact commits, sources, commands, costs, intervals, state/exposure artifacts, and replay requirements remain to be inventoried and separately frozen.

## Distinction from prior Core work

Existing Core v1 work already includes:

- allocation robustness;
- risk-sleeve ablation;
- cost sensitivity;
- regime attribution;
- historical event and regime analysis.

Campaign #52 must not duplicate those studies.

Its distinct question is whether authentic chronological alignment adds value after preserving non-timing characteristics as closely as a frozen counterfactual design permits.

## Proposed counterfactual classes

Planning candidates only; none is selected or authorized for generation.

1. **Static exposure-matched control** — preserve predetermined average composition while removing dynamic state timing.
2. **Deterministically displaced state sequence** — preserve sequence order and durations but apply decisions at fixed, preselected offsets.
3. **Deterministic block-permuted state sequence** — preserve approximate prevalence, duration, exposure distribution, and activity while destroying authentic chronology.

## Interpretation targets

Campaign #52 is intended to distinguish among:

1. chronological state value;
2. static allocation value;
3. capital-protection value concentrated in drawdown control, loss containment, or recovery rather than raw return.

These are interpretation targets, not frozen pass rules.

## Mandatory controls against self-confirmation

Before any outcome comparison, Campaign #52 must separately freeze:

- canonical Core v1 reference commit and configuration;
- source identities and date intervals;
- cost and cash-yield treatment;
- exact intervention object: state, signal, target, exposure, or order series;
- static-matching method;
- displacement values;
- block construction and deterministic permutation procedure;
- number of controls and multiplicity family;
- primary and secondary metrics;
- superiority, equivalence, support, and negative-result rules;
- deterministic artifacts and replay identities.

Core v1 logic, thresholds, weights, ordering, costs, or execution assumptions may not be changed in response to Campaign #52 results.

## Current authorization

**Decision:** GO for reference-artifact and intervention feasibility inventory only.

Authorized now:

- inspect existing Core v1 manifests, canonical commands, source identities, cost assumptions, state/exposure artifacts, and deterministic replay records;
- identify the exact series that could serve as the chronology intervention object without modifying strategy logic;
- determine whether static exposure matching, deterministic displacement, and deterministic block permutation are mechanically feasible;
- identify overlap with prior Core studies and exclude duplicated questions;
- inspect source and artifact structure without generating counterfactuals or performance results;
- draft `docs/research/CAMPAIGN_52_REFERENCE_INTERVENTION_FEASIBILITY_INVENTORY.md`;
- return to this board for a separate hypothesis-family-selection decision.

Not authorized:

- running canonical Core v1 or any counterfactual;
- generating shifted, permuted, randomized, or static-matched state, signal, target, exposure, order, return, or NAV series;
- calculating or comparing CAGR, Sharpe, Calmar, drawdown, recovery, cost, or any other performance metric;
- selecting controls based on Campaign #52 outcomes;
- fitting models or computing p-values, rankings, or support decisions;
- changing Core v1 runtime, thresholds, regime logic, classifier logic, signal logic, strategy logic, order behavior, execution, portfolio weights, NAV, exposure, dashboard, or model training;
- paper trading or live execution;
- accessing any separately protected holdout not explicitly authorized later.

## Mandatory stage separation

1. Planning charter — **completed**.
2. Reference-artifact and intervention feasibility inventory — **authorized next**.
3. Hypothesis-family selection — **not authorized**.
4. Frozen statistical specification — **not authorized**.
5. Implementation and synthetic tests — **not authorized**.
6. Development and validation execution — **not authorized**.
7. Untouched confirmation or prospective observation — **not authorized**.
8. Economic, paper, or runtime action — **not authorized**.

Passing one stage does not authorize the next.

## Immediate sequence

1. Inventory the canonical Core v1 reference and exact artifact lineage.
2. Identify whether chronology can be isolated at the state, target, exposure, or order layer without strategy modification.
3. Assess deterministic static, displaced, and block-permuted control feasibility.
4. Exclude designs that leak future information or merely repeat allocation/ablation work.
5. Return to the board before selecting any counterfactual family.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
