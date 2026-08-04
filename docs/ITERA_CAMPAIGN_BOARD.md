# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

No production or portfolio behavior is authorized unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** GOVERNED EQUIVALENCE RUNNER PERFORMANCE CORRECTION COMMITTED — local governed-source capture/replay equivalence evidence is still required. Counterfactual generation, performance metrics, development/validation comparisons, and runtime or strategy changes remain prohibited.

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

## Frozen design

- Core reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- exactly 20 controls: one static, lags `24h`, `168h`, `672h`, and sixteen 28-day block permutations
- no Core logic, weights, thresholds, costs, folds, or execution semantics may change

## Interrupted-run evidence

The local governed equivalence run started at `13:33:54` and was interrupted after more than two hours while capture mode repeatedly recomputed trend indicators over every growing dataframe prefix. The traceback terminated in `trend_following_v8._atr(...).ewm(...).mean()`.

This was a runner complexity defect, not a Campaign #52 result. No PASS manifest was produced. No counterfactuals or Campaign #52 performance metrics were generated.

## Performance correction

The corrected runner:

- executes the unchanged canonical strategy once per sleeve/fold;
- requires one canonical intent for every dataframe timestamp;
- reuses that exact canonical `StrategyIntent` sequence for the capture adapter;
- validates intent sequence against each chronological dataframe prefix;
- still runs capture and unchanged-target replay through unchanged execution mechanics;
- runs the two required independent passes concurrently by default in separate directories;
- provides fold and sleeve progress messages;
- preserves all equivalence comparisons and deterministic artifact hashing.

This correction does not precompute approximate indicators, shorten history, alter strategy logic, change thresholds, or modify runtime behavior.

## Governed equivalence runner contract

The runner must:

- verify all six frozen source hashes before execution;
- run canonical, capture-only, and unchanged-target replay paths only;
- compare sleeve equity, realized exposure, and trade economics;
- compare fold fund NAV and stitched NAV;
- repeat independently twice;
- require identical artifact SHA-256 maps;
- write a PASS manifest only after all checks succeed.

Replay audit reason text is excluded from economic trade equivalence; timestamps, directions, prices, quantities, notionals, fees, slippage, spread, cost basis points, exposures, and strategy identities remain included.

## Current authorization

**Decision:** HOLD pending focused optimization tests and exact local output from the corrected governed equivalence runner.

Authorized now:

- pull the performance correction and regression tests;
- run `tests/test_campaign52_governed_equivalence_runner.py` and `tests/test_campaign52_target_replay.py` only;
- execute `python -m scripts.run_campaign52_governed_equivalence` using the six governed defaults;
- inspect only command output and equivalence/artifact manifests;
- correct runner defects without changing the frozen Campaign #52 design;
- report exact output and manifest identities;
- return to this board for a separate development-execution decision.

Not authorized:

- generating static, lagged, or block-permuted controls;
- calculating Campaign #52 performance metrics, bootstrap inference, multiplicity, rankings, or support decisions;
- development or validation outcome comparison;
- changing Core behavior, sources, weights, thresholds, costs, folds, orders, execution, runtime, dashboard, or model training;
- paper trading or live execution.

## Stage separation

1. Planning — completed.
2. Feasibility — completed.
3. Family selection — completed.
4. Statistical specification — completed.
5. Source/calendar preflight — PASS.
6. Capture/replay implementation and synthetic validation — PASS.
7. Governed-source capture/replay equivalence runner — performance correction committed; local evidence pending.
8. Development/validation execution — not authorized.
9. Prospective confirmation — not authorized.
10. Economic, paper, or runtime action — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
