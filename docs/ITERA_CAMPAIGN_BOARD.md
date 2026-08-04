# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** FAMILY SELECTED — planning, intervention feasibility, and pre-outcome hypothesis-family selection are complete. A frozen statistical specification is the next authorized deliverable. Canonical Core execution, target capture, counterfactual generation, replay implementation, NAV reconstruction, metric calculation, model fitting, protected-stage access, and runtime/strategy changes remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Determine whether canonical Core v1 derives material value from the correct chronological alignment of its state-conditioned decisions, beyond what can be explained by average exposures, sleeve composition, and activity profile.

Campaign #52 is an architecture-falsification campaign. It is not a new directional-feature search and does not reopen Campaign #51.

## Governed antecedents

Campaign #51 is permanently closed as a governed negative result:

- closure: `docs/research/CAMPAIGN_51_FINAL_CLOSURE.md`;
- commit: `f9858cf8ceacb669f69d569250410ae289c6126d`;
- discovery supported: `0` of `12`;
- shortlist: empty;
- 2025 analytical values untouched;
- replay artifacts byte-identical.

## Campaign #52 governed records

- planning charter: `docs/research/CAMPAIGN_52_CORE_V1_CHRONOLOGICAL_STATE_VALUE_PLANNING_CHARTER.md`; commit `8ad9f3aae3dc4b36010ef8f723ae1c88bbf7db9d`;
- reference and intervention feasibility inventory: `docs/research/CAMPAIGN_52_REFERENCE_INTERVENTION_FEASIBILITY_INVENTORY.md`; commit `a86eba5392e57e936d65c4eb46207cb51c03b309`;
- hypothesis-family selection: `docs/research/CAMPAIGN_52_HYPOTHESIS_FAMILY_SELECTION.md`; commit `e2aa9ceafe531e11bea7040fe4309ac9e65b8ab2`.

## Planning reference

The planning reference remains the blessed Core v1 candidate documented in:

- `research/trade_idea_radar/CORE_V1_BASELINE_MANIFEST.md`;
- allocation: trend `0.40`, equity `0.35`, gold `0.15`, hedge `0.10`, mean reversion `0.00`;
- defining architecture: explicit BTC macro-state ownership across crypto trend sleeves.

This is not yet a frozen Campaign #52 execution reference.

The old baseline manifest command uses 2019-start crypto files. Later accepted Core work requires canonical 2018-start BTC and ETH sources. Exact commit, scenario, source hashes, date intervals, fold rules, costs, and reference artifacts must be frozen before implementation.

## Selected intervention object

The primary intervention object is each sleeve's **signed target-exposure stream derived from canonical strategy intents before execution**.

This layer:

- is common across all sleeves;
- preserves canonical strategy output before intervention;
- permits static, displaced, and block-permuted controls;
- permits replay through unchanged cooldown, threshold, fee, spread, slippage, cash-yield, and mark-to-market mechanics;
- separates chronology intervention from Core strategy modification.

Rejected primary intervention layers:

- raw BTC state only — too narrow for the complete portfolio;
- realized positions — already embed execution;
- executed orders — too downstream and potentially incoherent;
- NAV or returns — invalid for architecture testing.

## Selected counterfactual family

### Static composition control

- exactly `1` development-frozen static sleeve-target control;
- one fixed signed target per sleeve derived from development-stage canonical targets only;
- reused unchanged in later authorized stages;
- exact statistic and maintenance rule remain to be frozen.

### Causal positive displacement

- at most `3` positive fixed-displacement controls;
- preserve target values, order, and local duration structure;
- apply decisions later;
- no negative displacement;
- no wraparound;
- exact offsets and boundary rules remain to be frozen.

### Deterministic block permutation

- at most `16` stage-contained block-permutation controls;
- fixed non-overlapping wall-clock blocks;
- within-block order preserved;
- complete blocks permuted only within the same stage;
- exact duration, terminal-block rule, seeds, and permutation count remain to be frozen.

### Family ceiling

- static: `1`;
- positive displacement: at most `3`;
- block permutations: at most `16`;
- total counterfactual ceiling: `20`.

Canonical Core v1 is the fixed reference and is not counted as a counterfactual.

A later specification may select fewer controls for pre-outcome mechanical, calendar, or multiplicity reasons. It may not exceed 20 or add another control class.

## Excluded scope

Campaign #52 excludes:

- explicit-BTC-state-only confirmatory family;
- negative or leading displacement;
- allocation optimization;
- sleeve removal or capital redistribution;
- risk-sleeve ablation;
- cost sensitivity repetition;
- regime attribution of existing NAV;
- event-window summaries;
- policy-selector optimization;
- order reassignment;
- realized-position shifting;
- NAV or return rearrangement;
- new predictor searches.

## Required capture-and-replay invariants

Before any outcome execution, a later implementation must prove:

- capture-only execution is identical to canonical Core;
- replay of the unmodified target stream reproduces canonical targets, trades, costs, exposure, and NAV under a frozen serialization contract;
- interventions cannot alter sources, strategy logic, regime logic, weights, costs, cooldowns, thresholds, cash yield, folds, or execution assumptions;
- transformations are deterministic and stage-contained;
- later-stage targets or outcomes cannot parameterize earlier-stage controls;
- every artifact carries source, commit, scenario, transformation, seed, stage, and hash lineage.

## Safety state

At family selection:

- canonical Core run executed: `false`;
- target stream generated: `false`;
- counterfactual generated: `false`;
- realized exposure generated: `false`;
- orders generated: `false`;
- NAV generated: `false`;
- performance metrics calculated: `false`;
- outcomes inspected: `false`;
- runtime modified: `false`;
- strategy modified: `false`;
- weights modified: `false`.

## Current authorization

**Decision:** GO to draft and freeze a statistical specification only.

Authorized now:

- freeze the exact canonical Core v1 commit, scenario, weights, source identities, source hashes, intervals, fold construction, costs, and cash-yield treatment;
- define development, validation, and any untouched confirmation or prospective stage;
- freeze target serialization and native-timestamp alignment rules;
- freeze the static-target statistic and maintenance rule;
- select up to three exact positive offsets and define uncovered-boundary treatment;
- select block duration, terminal-block rule, deterministic seed derivation, canonical permutation order, and final permutation count up to sixteen;
- define primary and secondary metrics;
- define inferential unit, uncertainty procedure, multiplicity treatment, equivalence or superiority margins, and pass rules;
- define chronological-value, static-allocation-value, capital-protection-value, and negative-result interpretations;
- define deterministic artifact and replay requirements;
- inspect no Campaign #52 targets, counterfactual outcomes, NAVs, or performance metrics while doing so;
- update this board with the frozen specification and a separate implementation-authorization decision.

Not authorized:

- running canonical Core v1 or any counterfactual;
- capturing or generating target, state, signal, position, order, return, NAV, or metric series;
- implementing capture-and-replay code;
- selecting parameters based on Campaign #52 outcomes;
- calculating CAGR, Sharpe, Calmar, drawdown, recovery, costs, p-values, rankings, or support decisions;
- accessing a protected confirmation or holdout stage;
- changing Core v1 runtime, thresholds, regime logic, classifier logic, signal logic, strategy logic, order behavior, execution, portfolio weights, NAV, exposure, dashboard, or model training;
- paper trading or live execution.

## Mandatory stage separation

1. Planning charter — **completed**.
2. Reference-artifact and intervention feasibility inventory — **completed**.
3. Hypothesis-family selection — **completed**.
4. Frozen statistical specification — **authorized next**.
5. Implementation and synthetic tests — **not authorized**.
6. Development and validation execution — **not authorized**.
7. Untouched confirmation or prospective observation — **not authorized**.
8. Economic, paper, or runtime action — **not authorized**.

Passing one stage does not authorize the next.

## Immediate sequence

1. Freeze the exact Core reference and source lineage.
2. Freeze stage separation and target serialization.
3. Freeze static, lag, and block-permutation parameters within the selected family ceiling.
4. Freeze metrics, inference, multiplicity, margins, interpretation, and replay rules.
5. Return to the board for a separate implementation decision.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
