# Campaign #52 — Core v1 Chronological State Value Planning Charter

## Status

Planning only. No counterfactual generation, NAV reconstruction, performance comparison, model fitting, threshold change, allocation change, runtime change, or strategy modification is authorized by this charter.

## Research question

> Does canonical Core v1 derive material value from the correct chronological alignment of its state-conditioned decisions, beyond what can be explained by its average exposures, sleeve composition, and activity profile?

Campaign #52 is an architecture-falsification campaign. It is not a search for another standalone directional predictor and it is not a post-hoc modification of Campaign #51.

## Motivation

Campaign #48 found supported associations involving BTC volatility, drawdown, and future movement magnitude or volatility.

Campaigns #50 and #51 did not establish governed directional support from the tested standalone or interaction-based families.

Those negative results do not validate Core v1. They do motivate a distinct question: whether Core v1's observed historical behavior depends on chronologically correct state decisions rather than merely favorable average holdings or portfolio composition.

Existing Core v1 work already includes allocation robustness, risk-sleeve ablation, cost sensitivity, and regime attribution. Campaign #52 must not repeat those studies. Its distinguishing intervention is deliberate destruction of timing alignment while preserving non-timing characteristics as closely and transparently as the frozen design permits.

## Reference architecture boundary

Campaign #52 must use one separately frozen canonical Core v1 reference configuration and artifact lineage.

The current planning reference is the blessed Core v1 candidate documented in:

- `research/trade_idea_radar/CORE_V1_BASELINE_MANIFEST.md`;
- promoted allocation: trend `0.40`, equity `0.35`, gold `0.15`, hedge `0.10`, mean reversion `0.00`;
- explicit BTC macro-state ownership across crypto trend sleeves.

This planning reference is not yet a frozen Campaign #52 execution reference. A later source-and-artifact inventory must identify exact commits, commands, source files, costs, date intervals, canonical outputs, and replay requirements before family selection.

## Proposed counterfactual classes

The following classes are planning candidates only. None is selected or authorized for execution.

### 1. Static exposure-matched control

Construct a non-dynamic portfolio using predetermined exposure summaries derived only from the authorized reference interval and method.

Purpose:

> Test whether Core v1's broad asset and sleeve composition explains most of its observed behavior without state timing.

Open planning questions include whether matching occurs at sleeve, asset, gross-exposure, or net-exposure level and how cash or BIL treatment is preserved.

### 2. Deterministically displaced state sequence

Apply the canonical state or target-exposure sequence at one or more predetermined temporal offsets while preserving sequence order and duration.

Purpose:

> Preserve the shape and frequency of Core v1 decisions while breaking their correct market alignment.

Displacement values, boundary behavior, warmup treatment, and permissible data interval must be frozen before results.

### 3. Deterministic block-permuted state sequence

Partition the canonical decision or target-exposure sequence into predetermined contiguous blocks and reorder them using a fixed, replay-safe permutation rule.

Purpose:

> Preserve approximate state prevalence, duration, exposure distribution, and activity while destroying authentic chronology.

Block length, number of permutations, seeds or permutation identities, boundary rules, and multiplicity treatment must be frozen before results.

## Primary interpretation targets

Campaign #52 should distinguish among three possible mechanisms:

1. **Chronological state value:** canonical timing materially outperforms exposure- and activity-matched timing-destroyed controls.
2. **Static allocation value:** average composition explains most of the observed result; dynamic timing adds limited incremental value.
3. **Capital-protection value:** chronology contributes primarily through drawdown reduction, loss containment, or recovery rather than higher raw return.

These are interpretation targets, not frozen pass rules.

## Candidate metrics for later selection

A later statistical specification may consider a narrow, preselected set such as:

- compounded return or CAGR;
- annualized volatility;
- Sharpe;
- Calmar;
- maximum drawdown;
- worst rolling 21-day and 63-day return;
- drawdown duration or recovery duration;
- downside capture;
- turnover and estimated cost burden.

No metric set, weighting, composite score, superiority margin, or acceptance rule is selected by this charter.

## Required controls against self-confirmation

Campaign #52 must fail closed against becoming a post-hoc defense of Core v1.

Before any outcome comparison, the campaign must freeze:

- exact Core v1 reference commit and configuration;
- exact source identities and date boundaries;
- exact cost and cash-yield treatment;
- exact state, signal, target, exposure, or order series used as the intervention object;
- static-matching method;
- displacement values;
- block construction and deterministic permutation procedure;
- number of controls and multiplicity family;
- primary and secondary metrics;
- support, superiority, equivalence, and negative-result rules;
- deterministic artifact formats and replay identities.

Core v1 logic, thresholds, weights, ordering, costs, and execution assumptions may not be changed in response to Campaign #52 results.

## Leakage and chronology requirements

All interventions must be observation-only and deterministic.

Planning and later implementation must ensure:

- no future information enters canonical Core v1 decisions;
- no counterfactual uses future returns to choose shifts, blocks, permutations, exposures, or metrics;
- development, validation, and any holdout stages remain chronologically separated if adopted;
- exposure matching does not silently use prohibited future-stage summaries;
- block or displacement boundaries are explicit and fail closed;
- missing source or reference artifacts cause failure rather than substitution.

## Relationship to existing Core studies

Campaign #52 must not reinterpret prior allocation, sleeve-ablation, cost-sensitivity, or regime-attribution results as Campaign #52 evidence.

Those records may establish provenance and prevent duplicated work. They do not answer whether authentic chronology outperforms timing-destroyed controls.

## Planning sequence

1. **Planning charter** — this document.
2. **Reference-artifact and intervention inventory** — identify the canonical Core v1 run, state/exposure artifacts, source identities, costs, and whether timing controls can be generated without strategy modification.
3. **Hypothesis-family selection** — select a narrow counterfactual family and fixed count.
4. **Frozen statistical specification** — freeze intervals, transformations, metrics, inference, multiplicity, and pass rules.
5. **Implementation and synthetic tests** — only after a separate GO.
6. **Development and validation execution** — only after a separate GO.
7. **Untouched confirmation or prospective observation** — only if separately authorized.
8. **Any economic, paper, or runtime action** — outside this campaign unless separately authorized.

Passing one stage does not authorize the next.

## Current authorization boundary

Authorized after this charter is accepted:

- inspect existing Core v1 manifests, canonical commands, source identities, cost assumptions, state/exposure artifacts, and replay records;
- determine whether static exposure matching, deterministic displacement, and deterministic block permutation are mechanically feasible;
- document overlap with prior Core v1 studies;
- draft a source-and-intervention feasibility inventory without generating counterfactual NAVs or performance results.

Not authorized:

- running canonical Core v1 or any counterfactual;
- generating shifted, permuted, or static-matched exposure series;
- reconstructing NAV or returns;
- comparing performance metrics;
- choosing controls based on observed Campaign #52 outcomes;
- modifying Core v1 strategy logic, thresholds, ordering, allocation, costs, orders, NAV, or exposure;
- paper trading or live execution;
- accessing any separately protected holdout not explicitly authorized later.

## Success condition for the planning stage

The planning stage succeeds only if a later inventory can identify a narrow, deterministic, replay-safe, leakage-safe counterfactual family that genuinely isolates chronology and does not merely repeat existing allocation or ablation studies.

If that cannot be established, Campaign #52 must stop before family selection.
