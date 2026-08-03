# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** FEASIBILITY COMPLETE — reference-artifact and intervention inventory committed; pre-outcome hypothesis-family selection is the next authorized deliverable. Core execution, target capture, counterfactual generation, NAV reconstruction, metric comparison, model fitting, holdout access, and runtime/strategy changes remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Determine whether canonical Core v1 derives material value from the correct chronological alignment of its state-conditioned decisions, beyond what can be explained by average exposures, sleeve composition, and activity profile.

Campaign #52 is an architecture-falsification campaign. It is not another standalone directional-feature search and it does not reopen Campaign #51.

## Governed antecedents

### Campaign #51

Campaign #51 is permanently closed as a governed negative result:

- final closure: `docs/research/CAMPAIGN_51_FINAL_CLOSURE.md`;
- closure commit: `f9858cf8ceacb669f69d569250410ae289c6126d`;
- discovery supported: `0` of `12`;
- validation eligible: `0`;
- shortlist: empty;
- 2025 analytical values: untouched;
- canonical replay artifacts: byte-identical.

Campaign #51 may not be reopened through Campaign #52.

## Campaign #52 governed records

- planning charter: `docs/research/CAMPAIGN_52_CORE_V1_CHRONOLOGICAL_STATE_VALUE_PLANNING_CHARTER.md`; commit `8ad9f3aae3dc4b36010ef8f723ae1c88bbf7db9d`;
- reference and intervention feasibility inventory: `docs/research/CAMPAIGN_52_REFERENCE_INTERVENTION_FEASIBILITY_INVENTORY.md`; commit `a86eba5392e57e936d65c4eb46207cb51c03b309`.

## Planning reference

The current planning reference is the blessed Core v1 candidate documented in:

- `research/trade_idea_radar/CORE_V1_BASELINE_MANIFEST.md`;
- allocation: trend `0.40`, equity `0.35`, gold `0.15`, hedge `0.10`, mean reversion `0.00`;
- defining architecture: explicit BTC macro-state ownership across crypto trend sleeves.

This is not yet a frozen Campaign #52 execution reference.

The baseline manifest contains an older 2019-start validation command. Later accepted Core work requires canonical 2018-start BTC and ETH sources. Exact source hashes, reference commit, scenario, costs, interval, fold rules, and artifact identities remain to be frozen by later gates.

## Feasibility conclusion

Campaign #52 is mechanically feasible without modifying Core v1 strategy logic.

The strongest common intervention candidate is the sleeve-level **signed target-exposure stream derived from canonical strategy intents before execution**.

Rationale:

- common across all sleeves;
- preserves canonical strategy output before intervention;
- permits static, displaced, and block-permuted controls;
- permits replay through unchanged cooldown, threshold, fee, spread, slippage, cash-yield, and mark-to-market mechanics;
- separates chronology intervention from Core strategy modification.

Other layers:

- raw BTC macro-state columns: feasible only as a narrow secondary crypto-trend attribution;
- realized positions: useful for matching diagnostics, rejected as primary because they already embed execution;
- executed orders: rejected as too downstream and potentially incoherent after displacement;
- NAV or return series: rejected.

## Mechanically feasible counterfactual classes

Planning candidates only; none is frozen or authorized for generation.

1. **Development-frozen static sleeve target** — composition control with no authentic timing.
2. **Positive fixed displacement of target streams** — preserves sequence and duration while applying decisions late; causal if no wraparound is allowed.
3. **Deterministic stage-contained block permutation** — preserves within-block order and approximate state persistence while destroying authentic long-run chronology.
4. **Secondary explicit-BTC-state intervention** — narrow crypto-trend attribution only.

Negative displacement that applies future targets earlier is look-ahead contaminated and must not enter confirmatory support claims.

## Existing Core work excluded from duplication

Campaign #52 must not repeat:

- allocation optimization;
- sleeve removal or capital redistribution;
- risk-sleeve ablation;
- cost sensitivity;
- regime attribution of existing NAV;
- event-window summaries;
- policy-selector optimization;
- a fresh directional-feature search.

## Required later invariants

Before any governed outcome execution, a capture-and-replay adapter must prove:

- capture-only canonical execution is unchanged;
- replay of the unmodified captured target stream reproduces canonical trades, costs, exposure, and NAV under a frozen serialization contract;
- interventions cannot alter sources, strategy logic, regime logic, weights, costs, cooldowns, thresholds, cash yield, fold order, or execution assumptions;
- all transformations are deterministic and stage-contained;
- later-stage targets or outcomes cannot parameterize earlier-stage controls;
- every artifact carries full source, commit, scenario, transformation, seed, stage, and hash lineage.

## Safety state

At completion of the feasibility inventory:

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

**Decision:** GO to select and document a narrow pre-outcome hypothesis family only.

Authorized now:

- select the exact intervention object from the mechanically valid candidates;
- select a narrow set of static, causal displacement, and/or deterministic block-permutation control families;
- define the conceptual comparison and interpretation boundaries;
- set an ex ante candidate-count ceiling;
- exclude noncausal, duplicated, economically incoherent, or execution-bypassing controls;
- document the selection in `docs/research/CAMPAIGN_52_HYPOTHESIS_FAMILY_SELECTION.md`;
- inspect no Campaign #52 performance outcomes while selecting the family;
- return to this board for a separate statistical-specification decision.

Not authorized:

- running canonical Core v1 or any counterfactual;
- generating or inspecting target, state, signal, position, order, return, NAV, or metric series;
- selecting offsets, blocks, seeds, controls, or metrics based on Campaign #52 outcomes;
- freezing a statistical specification;
- implementing a capture-and-replay adapter;
- calculating CAGR, Sharpe, Calmar, drawdown, recovery, costs, p-values, rankings, or support decisions;
- changing Core v1 runtime, thresholds, regime logic, classifier logic, signal logic, strategy logic, order behavior, execution, portfolio weights, NAV, exposure, dashboard, or model training;
- paper trading or live execution;
- accessing any separately protected holdout.

## Mandatory stage separation

1. Planning charter — **completed**.
2. Reference-artifact and intervention feasibility inventory — **completed**.
3. Hypothesis-family selection — **authorized next**.
4. Frozen statistical specification — **not authorized**.
5. Implementation and synthetic tests — **not authorized**.
6. Development and validation execution — **not authorized**.
7. Untouched confirmation or prospective observation — **not authorized**.
8. Economic, paper, or runtime action — **not authorized**.

Passing one stage does not authorize the next.

## Immediate sequence

1. Select the pre-execution signed target-exposure intervention object or document a justified alternative.
2. Select a compact control family that separates static composition from authentic chronology.
3. Exclude negative displacement, order reassignment, and NAV rearrangement.
4. Freeze only the hypothesis-family inventory and candidate-count ceiling.
5. Return to the board before statistical specification or implementation.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
