# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

No production or portfolio behavior is authorized unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** DEVELOPMENT-ONLY EXECUTION PROCEDURE COMMITTED — explicit authorization is required before implementing development tooling. Control generation, governed replay, performance metrics, inference, development outcomes, validation access, and runtime or strategy changes remain prohibited.

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
- synthetic tests: `1adb2c255bbd56e2332ceada15862f7a10d70c99`
- synthetic PASS evidence: `d7e786ff97375f47b9a0343076fc2cb4afc4e0e8`
- governed equivalence runner: `92b274c57c2cca2a3ac094896894779a7bb0a42a`
- governed runner implementation record: `4c6edda17861fc36c9580679f3a589fe7b0a128d`
- HOLD exposure validation correction: `105cc81e8d5dd5b2d158e088b717adfae52292df`
- HOLD validation regression tests: `184229dafc2f4b96bdb43b3135e6a6e1f5e339ea`
- governed runner performance correction: `0da89d7af340ca8bdb629ce29ee09cfbb683f971`
- governed runner optimization tests: `1017fdffaa2e6abe5b1d5b40988380dfe0676baa`
- governed-source equivalence PASS evidence: `docs/research/CAMPAIGN_52_GOVERNED_EQUIVALENCE_PASS_EVIDENCE.md`; commit `0db3875d2c181f65b41e06145825f7d5363226e4`
- development-only execution procedure: `docs/research/CAMPAIGN_52_DEVELOPMENT_EXECUTION_PROCEDURE.md`; commit `af30879a0f37b4a635780a9cea5e8cf2b2590e29`

## Frozen design

- Core reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- exactly 20 controls: one static, lags `24h`, `168h`, `672h`, and sixteen 28-day block permutations
- no Core logic, weights, thresholds, costs, folds, or execution semantics may change

## Governed-source equivalence result

The corrected local governed-source equivalence run reported:

- `status: PASS`;
- all six frozen source SHA-256 identities matched;
- canonical versus capture equivalence passed;
- capture versus unchanged-target replay equivalence passed;
- sleeve equity, realized exposure, trade economics, fold fund NAV, and stitched NAV checks passed;
- two independent passes produced identical artifact SHA-256 maps;
- no counterfactuals, Campaign performance metrics, bootstrap, runtime modification, strategy modification, or weight modification occurred.

The uninterrupted successful run began at 08:27 local time on 2026-08-05. An earlier run stopped for computer shutdown is not evidence.

This is an implementation/equivalence gate only. It is not a Campaign #52 alpha, performance, statistical, development-versus-validation, ranking, support, or economic result.

## Development procedure result

The committed development-only procedure freezes:

- import and hash verification of the existing governed equivalence target artifacts;
- structural prohibition on opening validation paths;
- exact construction of the static, lagged, and 16 deterministic block-permutation controls;
- two-pass transformation identity before any replay;
- unchanged target replay and canonical import-integrity checks;
- fold, stitched hourly, and daily end-of-day NAV construction;
- primary and secondary metrics;
- paired 21-day moving-block bootstrap with 10,000 replications;
- deterministic seed derivation and Holm adjustment across all 20 controls;
- the frozen development support rule;
- two-pass artifact identity, atomic output promotion, and fail-closed conditions;
- required synthetic tests and runtime safeguards.

The procedure explicitly reuses the already validated canonical target artifacts and prohibits rerunning canonical strategy evaluation during development execution.

This is a procedure record only. It contains no generated control, replay, metric, inference, ranking, or development decision.

## Current authorization

**Decision:** HOLD pending explicit authorization to implement observation-only development tooling and synthetic tests.

Authorized now:

- inspect and review the committed development-only execution procedure;
- correct procedure-record defects without changing the frozen Campaign #52 design;
- decide whether to authorize implementation of deterministic, observation-only, fail-closed development tooling and synthetic tests.

Not authorized:

- implementing development tooling before a separate explicit board authorization;
- generating static, lagged, or block-permuted controls;
- replaying canonical or control development outcomes;
- calculating return, drawdown, Calmar, bootstrap inference, multiplicity, rankings, or support decisions;
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
8. Development execution procedure — completed; implementation not authorized.
9. Development tooling and synthetic validation — not authorized.
10. Governed development execution — not authorized.
11. Validation execution — not authorized.
12. Prospective confirmation — not authorized.
13. Economic, paper, or runtime action — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
