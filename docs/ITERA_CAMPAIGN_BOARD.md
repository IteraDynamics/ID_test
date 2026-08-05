# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

No production or portfolio behavior is authorized unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** DEVELOPMENT NEGATIVE — the governed 2020-2022 hypothesis test completed successfully and failed the frozen development gate. Campaign #52 does not advance to validation. Development-result interpretation is authorized; validation access and all runtime or strategy changes remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

Determine whether canonical Core v1 derives material value from authentic chronological alignment of sleeve-level pre-execution signed target exposures.

## Governed records

- planning charter: `8ad9f3aae3dc4b36010ef8f723ae1c88bbf7db9d`
- feasibility inventory: `a86eba5392e57e936d65c4eb46207cb51c03b309`
- family selection: `e2aa9ceafe531e11bea7040fe4309ac9e65b8ab2`
- frozen statistical specification: `14a96b4078eec516570fce0c289baa061398a995`
- source/calendar evidence: `bd2af6c11991a637510122bdb4a3300b9653be14`
- capture/replay adapter: `bf5d7d7d7c18f23ddea6a1c622ce26359ef12393`
- governed-source equivalence PASS: `0db3875d2c181f65b41e06145825f7d5363226e4`
- development procedure: `af30879a0f37b4a635780a9cea5e8cf2b2590e29`
- development helper synthetic PASS: `04b1de5b145a451de38118d6d27562d0bdccfe53`
- governed development runner: `4443496290bdde5762edd8fe0deaf7a523be0c41`
- static-control correction: `98299130ebbc78fc3b0b2d5a98ff3e84ff988d5b`
- timezone and concurrent-pass correction: `c3f9208c3628b6cb4256b28bae0848a4b17c6d9a`
- calendar-compatible permutation amendment: `969cb63032822b57208c3bbcca173c45b0cc6828`
- amended permutation implementation: `752242281e1d079b8821a7510cb066e78e3ac4a9`
- irregular-calendar regression tests: `addfc084d5408b837af32ccb47d9d96f2acb9f68`
- replay-input caching: `abb3262f008d7d0038352cfa8b2bb4562125de6d`
- amendment implementation record: `bae64a8161fbff3a2345bc24ea9abe28494052db`
- development-negative result record: `f566958dc94fdff207355ad8f550720a80aeabb3`

## Frozen design

- Core reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- exactly 20 controls: one static, lags `24h`, `168h`, `672h`, and sixteen deterministic calendar-compatible 28-day block permutations
- primary endpoints: annualized geometric return, maximum drawdown magnitude, Calmar
- paired daily log-return inference: deterministic 21-day moving-block bootstrap, 10,000 replications
- Holm adjustment across all 20 controls within development
- no Core logic, weights, thresholds, costs, folds, orders, execution, NAV, or exposure semantics may change

## Development result

The governed development run completed with:

- status: `PASS`
- classification: `DEVELOPMENT_NEGATIVE`
- development gate passed: `false`
- independent passes: `2`
- controls: `20`
- bootstrap replications per control: `10,000`
- calendar-compatible block permutation: `true`
- validation targets opened: `false`
- canonical strategy invoked: `false`
- runtime, strategy, and weights modified: `false`

This is a valid negative development result under the frozen Campaign #52 rules. It is not a runtime or economic-action decision.

## Current authorization

Authorized now:

- inspect and summarize the promoted development artifacts;
- determine which frozen sub-rules failed;
- quantify canonical-versus-static, lag, and permutation differences;
- inspect adjusted p-values, confidence intervals, movable/fixed permutation blocks, and endpoint rankings;
- write a final Campaign #52 interpretation and closure record.

Still prohibited:

- opening, reading, replaying, transforming, or measuring validation targets or outcomes;
- changing Core behavior, sources, weights, thresholds, costs, folds, orders, execution, NAV, exposure, runtime, dashboard, or training;
- paper trading, live execution, or economic action;
- reframing or retesting Campaign #52 after seeing the result without a separately chartered new campaign.

## Stage separation

1. Planning — completed.
2. Feasibility — completed.
3. Family selection — completed.
4. Statistical specification — frozen.
5. Source/calendar preflight — PASS.
6. Capture/replay implementation and synthetic validation — PASS.
7. Governed-source capture/replay equivalence — PASS.
8. Development execution procedure — completed.
9. Development tooling and runner implementation — completed.
10. Governed development execution — **DEVELOPMENT_NEGATIVE**.
11. Development-result interpretation and closure — pending artifact review.
12. Validation execution — prohibited by development result.
13. Prospective confirmation — not authorized.
14. Economic, paper, or runtime action — not authorized.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
