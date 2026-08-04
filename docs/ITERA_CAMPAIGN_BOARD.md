# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** SOURCE/CALENDAR PREFLIGHT PASS — source identities and stage geometry are frozen. Capture/replay adapter implementation and synthetic equivalence tests are the next authorized deliverable. Canonical Core outcome execution, counterfactual generation, development/validation NAVs, performance metrics, and runtime/strategy changes remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

Determine whether canonical Core v1 derives material value from authentic chronological alignment of sleeve-level pre-execution signed target exposures, beyond static composition or chronology-destroyed controls replayed through identical execution mechanics.

## Governed records

- planning charter: `8ad9f3aae3dc4b36010ef8f723ae1c88bbf7db9d`
- reference/intervention feasibility inventory: `a86eba5392e57e936d65c4eb46207cb51c03b309`
- hypothesis-family selection: `e2aa9ceafe531e11bea7040fe4309ac9e65b8ab2`
- frozen statistical specification: `14a96b4078eec516570fce0c289baa061398a995`
- source/calendar preflight implementation: `597c32fd0b5ba3846b7ca74d13223ea3fdfa2ea1`
- inclusive-date correction: `0ba18dfcb0193fc267b07691cf81fb36efd46593`
- focused tests correction: `c3ce60580a973305da7c05e91cea656e91126a6f`
- source/calendar PASS evidence: `docs/research/CAMPAIGN_52_SOURCE_CALENDAR_PREFLIGHT_EVIDENCE.md`; commit `bd2af6c11991a637510122bdb4a3300b9653be14`

Focused synthetic tests were reported as passed. Exact pytest count/output was not supplied and is not asserted.

## Frozen Core reference

- repository reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- weights: BTC 1H trend `0.10`, BTC 4H trend `0.10`, ETH 1H trend `0.10`, ETH 4H trend `0.10`, BTC 1H hedge `0.05`, ETH 1H hedge `0.05`, SPY `0.175`, QQQ `0.175`, GLD `0.15`
- no mean-reversion sleeve
- no Core logic, threshold, cost, fold, order, execution, or weight change permitted

## Frozen stages and controls

- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- no untouched-2025 claim
- prospective confirmation requires future data and separate authorization

Exactly 20 controls:

1. one development-frozen static arithmetic-mean signed target per sleeve;
2. positive target lags of `24h`, `168h`, and `672h`;
3. sixteen deterministic stage/fold-contained permutations of complete `28`-day blocks.

Primary endpoints are annualized geometric return, maximum drawdown magnitude, and Calmar ratio. Inference uses paired daily log returns, a deterministic 21-day moving-block bootstrap with 10,000 replications, and Holm correction across all 20 controls separately within each stage. The authoritative details remain in `docs/research/CAMPAIGN_52_STATISTICAL_SPECIFICATION.md`.

## Frozen source identities

### BTC

- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- bytes: `4,792,028`
- rows: `70,069`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- missing expected hourly timestamps: `36`

### ETH

- SHA-256: `73721a1ef1dffbff64bf6ef2d92fb508a59b20d5c847684d96fdc7015912845f`
- bytes: `4,550,061`
- rows: `70,086`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- missing expected hourly timestamps: `19`

### SPY

- SHA-256: `85a24eb44e2377cdcb9c22b0f4062730d332ec276f371e71405e1cbfc0b8ac86`
- bytes: `213,839`
- rows: `2,010`
- coverage: `2018-01-02` through `2025-12-30`

### QQQ

- SHA-256: `34867c2b2da4aece23892b8e035e528f547173f3bc137cbe33b1295af0c1ff7b`
- bytes: `214,940`
- rows: `2,010`
- coverage: `2018-01-02` through `2025-12-30`

### BIL

- SHA-256: `8c7522487662bc65711deb5a784806fcdb5006f631d2359d3bbaaca9e226ae7a`
- bytes: `156,266`
- rows: `1,714`
- coverage: `2019-03-08` through `2025-12-30`

### GLD

- SHA-256: `f740b144a1ceea2ce85afdc503175a5e7c0f96a8cfbd6ddea3ed26cfed7d491b`
- bytes: `216,737`
- rows: `2,010`
- coverage: `2018-01-02` through `2025-12-30`

All six sources are strictly increasing, duplicate-free, and cover both retrospective stages under governed inclusive-calendar-date semantics. No substitution, repair, interpolation, fill, or acquisition is permitted.

## Frozen calendar facts

Each stage contains:

- `39` complete 28-day blocks;
- one terminal remainder of `4` days.

Exact lag mappings were verified for all six sources. Uncovered timestamps remain flat under the frozen design; no nearest matching, resampling, forward fill, wraparound, cross-stage carry, or cross-fold carry is permitted.

## Source-preflight safety state

The successful preflight reported all of the following false:

- prices parsed
- targets generated
- signals generated
- positions generated
- trades generated
- costs generated
- returns generated
- NAV generated
- performance metrics calculated
- capture/replay implemented
- runtime modified
- strategy modified
- weights modified

## Current authorization

**Decision:** GO for capture/replay adapter implementation and synthetic equivalence tests only.

Authorized now:

- implement an additive, research-only adapter that captures the signed target exposure implied by canonical `StrategyIntent` before execution;
- implement replay of an externally supplied target stream through unchanged cooldown, rebalance threshold, fill, fee, spread, slippage, cash-yield, and mark-to-market mechanics;
- preserve the canonical engine and strategy modules unchanged;
- implement deterministic target serialization under the frozen CSV contract;
- add synthetic tests proving action-to-signed-target conversion, signed long/short/flat handling, native timestamp preservation, cooldown and threshold preservation, cost preservation, cash-yield preservation, stage/fold isolation, fail-closed malformed-stream handling, and deterministic serialization;
- implement a synthetic capture-only versus canonical equivalence test;
- implement a synthetic unmodified-target replay equivalence test;
- document the implementation and return to this board for a separate source-backed equivalence-run decision.

Not authorized:

- running the adapter against the six governed Campaign #52 sources;
- generating or inspecting canonical Core targets from governed data;
- generating static, lagged, or permuted controls;
- generating governed trades, exposures, costs, returns, NAVs, or metrics;
- development or validation execution;
- bootstrap, multiplicity, rankings, or support decisions;
- changing Core v1 strategy, regime, thresholds, cooldowns, costs, weights, folds, order behavior, execution semantics, runtime, dashboard, or model training;
- paper trading or live execution.

## Mandatory stage separation

1. Planning charter — completed.
2. Reference-artifact/intervention feasibility — completed.
3. Hypothesis-family selection — completed.
4. Frozen statistical specification — completed.
5. Source-only identity/calendar preflight — **PASS**.
6. Capture/replay implementation and synthetic tests — **authorized next**.
7. Governed-source capture/replay equivalence run — not authorized.
8. Development/validation execution — not authorized.
9. Prospective confirmation — not authorized.
10. Economic, paper, or runtime action — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
