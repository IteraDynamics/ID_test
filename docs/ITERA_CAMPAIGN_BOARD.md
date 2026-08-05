# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

No production or portfolio behavior is authorized unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** DEVELOPMENT TOOLING AND SYNTHETIC TESTS COMMITTED — exact local focused-test output is required next. Governed artifact import, control generation, replay, metrics, inference, development outcomes, validation access, and runtime or strategy changes remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

Determine whether canonical Core v1 derives material value from authentic chronological alignment of sleeve-level pre-execution signed target exposures.

## Governed records

- planning charter: `8ad9f3aae3dc4b36010ef8f723ae1c88bbf7db9d`
- feasibility inventory: `a86eba5392e57e936d65c4eb46207cb51c03b309`
- family selection: `e2aa9ceafe531e11bea7040fe4309ac9e65b8ab2`
- frozen specification: `14a96b4078eec516570fce0c289baa061398a995`
- source/calendar evidence: `bd2af6c11991a637510122bdb4a3300b9653be14`
- capture/replay adapter: `bf5d7d7d7c18f23ddea6a1c622ce26359ef12393`
- synthetic capture/replay tests: `1adb2c255bbd56e2332ceada15862f7a10d70c99`
- governed-source equivalence PASS evidence: `0db3875d2c181f65b41e06145825f7d5363226e4`
- development-only execution procedure: `af30879a0f37b4a635780a9cea5e8cf2b2590e29`
- development tooling authorization: `82b1e920c5b0e1bd4918e62d9b13eed511463d1b`
- development helper implementation: `f9ef8eb41dbbdd9417b1ec0b85918da0e98d2898`
- development synthetic tests: `54ce33a0f3c9edc881aad69b8f5efbd913516e95`
- development tooling implementation record: `640ff3a3edd131c622b43e24fe4061742f88a662`

## Frozen design

- Core reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- exactly 20 controls: one static, lags `24h`, `168h`, `672h`, and sixteen 28-day block permutations
- no Core logic, weights, thresholds, costs, folds, or execution semantics may change

## Governed-source equivalence result

The governed-source equivalence gate passed with all six frozen source identities, canonical-versus-capture equality, capture-versus-replay equality, two independent artifact-identical passes, and no counterfactual or performance analysis.

This was an implementation gate only, not a Campaign #52 alpha or support result.

## Development tooling implementation

The committed pure helper module and fabricated-data tests cover:

- structural validation-path rejection;
- exact static, lagged, and deterministic block-permutation transformations;
- deterministic seed and Fisher-Yates behavior;
- terminal-block and row-count invariants;
- daily end-of-day NAV and primary metric conventions;
- deterministic 21-day, 10,000-replication moving-block bootstrap;
- exact 20-member Holm adjustment;
- development decision boundaries;
- atomic output promotion and stale-output rejection.

The implementation has no governed artifact discovery, source loading, strategy invocation, replay orchestration, or validation-stage access.

No governed target, control, replay, NAV, metric, inference, ranking, or development decision was generated or inspected.

## Current authorization

**Decision:** HOLD pending exact local output from:

`python -m pytest tests/test_campaign52_development.py -q`

Authorized now:

- pull the committed pure helper implementation and synthetic tests;
- run only the focused synthetic test file above;
- inspect and report exact test output;
- correct synthetic implementation defects without opening governed artifacts or changing the frozen design;
- return to this board for a separate synthetic-validation and governed-runner implementation decision.

Not authorized:

- opening governed equivalence target artifacts;
- implementing or running a governed development artifact importer or execution runner;
- generating governed static, lagged, or block-permuted controls;
- replaying canonical or control development outcomes;
- calculating or inspecting governed return, drawdown, Calmar, bootstrap, rankings, or support decisions;
- opening, reading, transforming, replaying, or measuring validation outcomes;
- comparing development and validation outcomes;
- changing Core behavior, sources, weights, thresholds, costs, folds, orders, execution, exposure, runtime, dashboard, or model training;
- paper trading or live execution.

## Stage separation

1. Planning — completed.
2. Feasibility — completed.
3. Family selection — completed.
4. Statistical specification — completed.
5. Source/calendar preflight — PASS.
6. Capture/replay implementation and synthetic validation — PASS.
7. Governed-source capture/replay equivalence — PASS.
8. Development execution procedure — completed.
9. Development tooling implementation and synthetic tests — committed.
10. Synthetic validation — **pending local evidence**.
11. Governed development runner implementation — not authorized.
12. Governed development execution — not authorized.
13. Validation execution — not authorized.
14. Prospective confirmation — not authorized.
15. Economic, paper, or runtime action — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
