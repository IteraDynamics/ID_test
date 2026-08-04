# Campaign #52 Hypothesis-Family Selection

## Decision

Select a narrow architecture-falsification family testing whether canonical Core v1 benefits from the authentic chronological alignment of its sleeve-level pre-execution signed target exposures.

This selection is made before any Campaign #52 canonical target capture, counterfactual generation, realized exposure, order, return, NAV, performance metric, ranking, model fit, p-value, support decision, or protected-stage access.

## Research question

> Does canonical Core v1 produce materially better return quality and capital-protection behavior when its authentic sleeve target decisions remain aligned to their original market chronology than when composition and activity characteristics are preserved as closely as possible but chronology is removed or delayed?

Campaign #52 does not ask whether a new predictor improves Core v1. It asks whether the timing already produced by frozen Core v1 contains value beyond broad composition and activity.

## Primary intervention object

The selected intervention object is:

- each sleeve's signed target-exposure stream derived from its canonical `StrategyIntent` before execution;
- represented at the sleeve's native decision timestamps;
- captured without changing strategy, regime, source, weight, threshold, cooldown, cost, cash-yield, fold, or execution logic;
- replayed through the unchanged execution engine after a separately required capture-and-replay equivalence gate.

This layer is selected because it is common across all sleeves and permits chronology intervention while retaining economically coherent fills, costs, cooldowns, thresholds, cash balances, and mark-to-market behavior.

Realized positions, executed orders, NAV, and return streams are excluded as intervention objects because they already embed downstream execution or outcomes.

## Selected counterfactual family

### 1. Development-frozen static sleeve-target control

One static composition control is selected.

Concept:

- derive one fixed signed target exposure separately for each sleeve using development-stage canonical targets only;
- reuse those development-frozen targets unchanged in later authorized stages;
- preserve canonical sleeve capital weights, sources, costs, cash yield, and execution settings;
- remove authentic dynamic timing.

The exact development statistic and maintenance rule remain to be frozen in the statistical specification.

Purpose:

- estimate how much of Core v1's behavior can be explained by broad sleeve composition without authentic target timing.

Candidate count:

- exactly `1` static control.

### 2. Causal positive-displacement controls

A compact family of lagging target-sequence controls is selected.

Concept:

- preserve each sleeve's canonical target values, order, and local duration structure;
- apply the sequence later by fixed positive wall-clock displacements;
- forbid negative displacement;
- forbid wraparound;
- treat uncovered stage boundaries under a separately frozen fail-closed rule;
- replay through unchanged execution.

Purpose:

- test whether correct timing matters when the same decisions are made late.

Candidate-count ceiling:

- no more than `3` positive displacement controls.

The exact positive offsets remain to be frozen before implementation and may not be selected from Campaign #52 outcomes.

### 3. Deterministic stage-contained block-permutation controls

A distributional placebo family is selected.

Concept:

- partition each sleeve target stream into fixed, non-overlapping wall-clock blocks;
- preserve within-block order;
- permute complete blocks only within the same governed stage;
- use deterministic, predeclared seed derivation and canonical permutation order;
- never use outcome metrics to select block duration, seeds, or retained permutations;
- replay through unchanged execution.

Purpose:

- preserve local persistence, target prevalence, and much of the activity profile while destroying authentic long-run chronological alignment.

Candidate-count ceiling:

- no more than `16` deterministic block-permutation controls.

The exact block duration, terminal-block rule, seed construction, and permutation count up to this ceiling remain to be frozen in the statistical specification.

## Family size ceiling

Maximum counterfactual count:

- static controls: `1`;
- positive displacement controls: at most `3`;
- block-permutation controls: at most `16`;
- total counterfactual ceiling: `20`.

Canonical Core v1 is the fixed reference and is not counted as a counterfactual.

The statistical specification may select fewer than 20 controls for mechanical, calendar, or multiplicity reasons documented before outcome execution. It may not exceed 20 or add a new control class.

## Primary conceptual comparison

The primary comparison is:

> canonical chronological Core v1 versus the frozen distribution of selected counterfactuals replayed through identical execution mechanics.

The campaign is intended to distinguish among three interpretations:

1. **Chronological state value** — canonical alignment materially exceeds composition- and activity-preserving controls.
2. **Static allocation value** — the static control reproduces much of Core's behavior and timing controls add little separation.
3. **Capital-protection value** — canonical timing adds limited raw return but materially improves drawdown, worst-loss, or recovery behavior.

These are interpretation categories, not yet pass rules.

## Primary and secondary scope

Primary scope:

- complete Core v1 portfolio;
- all active sleeves under one frozen canonical scenario;
- sleeve-level target intervention and unchanged execution replay.

Excluded from the selected family:

- explicit-BTC-state-only intervention;
- sleeve-specific exploratory intervention families;
- negative or leading displacement;
- trade or order reassignment;
- realized-position shifting;
- NAV or return rearrangement;
- allocation-weight changes;
- sleeve removal or capital redistribution;
- new predictor searches;
- policy-selector or optimization studies.

The BTC-state-only intervention remains mechanically feasible but is excluded to prevent Campaign #52 from fragmenting into a second attribution campaign.

## Pre-outcome rationale

### Why include a static control

Core v1 may benefit primarily from owning a favorable long-run mixture of trend, equity, gold, and hedge sleeves. A development-frozen static target control provides a direct composition benchmark without changing sleeve weights.

### Why include positive displacement

Positive displacement preserves the actual decision sequence more faithfully than static exposure while breaking contemporaneous alignment. It is causal, interpretable, and provides a direct test of whether making the same decisions late degrades outcomes.

### Why include block permutation

A single lag can interact idiosyncratically with market cycles. Stage-contained block permutations provide a broader placebo distribution while preserving within-block persistence and approximate activity.

### Why exclude negative displacement

Applying future targets earlier uses information unavailable at the decision timestamp. Such controls are look-ahead contaminated and cannot support confirmatory claims.

### Why cap the family at 20

A hard ceiling limits multiplicity, compute, interpretive flexibility, and post-outcome control selection while retaining one composition benchmark, a small set of interpretable timing lags, and a modest placebo distribution.

## Required invariants before execution

A later specification and implementation must fail closed unless they freeze and verify:

- exact canonical Core v1 commit, scenario, weights, sources, source hashes, date intervals, folds, and costs;
- exact target serialization at native sleeve timestamps;
- capture-only canonical equivalence;
- unmodified-target replay equivalence for targets, trades, costs, exposures, and NAV;
- development, validation, and any confirmation separation;
- development-only parameterization of the static control;
- exact positive offsets and boundary treatment;
- exact block duration, terminal-block rule, seed derivation, and permutation order;
- a multiplicity family that includes every selected control under the frozen inferential design;
- deterministic artifact serialization and replay hashes;
- no strategy, regime, weight, threshold, cooldown, cost, cash-yield, source, fold, or execution modification.

## Interpretation boundary

Family selection does not establish:

- that Core v1 contains chronological value;
- that Core v1 has alpha;
- that Core v1 beats static allocation;
- that Core v1 improves drawdown or recovery;
- that any counterfactual is feasible under the final source and calendar contract;
- economic superiority, deployment readiness, or live value.

No Campaign #52 outcome has been generated or inspected.

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

## Authorization boundary

This record selects the Campaign #52 hypothesis family only.

It does not authorize:

- canonical Core execution;
- target capture;
- counterfactual construction;
- replay implementation;
- NAV or performance generation;
- model fitting or inferential calculation;
- protected-stage or holdout access;
- economic testing beyond the later frozen campaign design;
- paper trading;
- runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes.
