# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

No production or portfolio behavior is authorized unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** SYNTHETIC CAPTURE/REPLAY PASS — governed-source capture/replay equivalence run is the next authorized stage. Counterfactual generation, development/validation execution, performance metrics, and runtime or strategy changes remain prohibited.

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
- implementation record: `fc23c02e8c2543f29f6378368ab65725576977b4`
- synthetic PASS evidence: `docs/research/CAMPAIGN_52_CAPTURE_REPLAY_SYNTHETIC_EVIDENCE.md`; commit `d7e786ff97375f47b9a0343076fc2cb4afc4e0e8`

## Synthetic evidence

Exact reported focused-test result:

```text
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collected 6 items
tests\test_campaign52_target_replay.py ...... [100%]
6 passed in 3.00s
```

This passes the synthetic implementation gate only. It does not establish governed-source equivalence or any Campaign #52 research outcome.

## Frozen design

- Core reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- exactly 20 controls: one static, lags `24h`, `168h`, `672h`, and sixteen 28-day block permutations
- no Core logic, weights, thresholds, costs, folds, or execution semantics may change

## Source state

The six governed source identities and calendar facts are frozen in `docs/research/CAMPAIGN_52_SOURCE_CALENDAR_PREFLIGHT_EVIDENCE.md`.

## Current authorization

**Decision:** GO for a governed-source capture/replay equivalence run only.

Authorized now:

- add a research-only runner that uses the six exact governed source paths and frozen `baseline_40_35_15_10` scenario;
- verify source hashes before any governed-source execution;
- run canonical capture-only and unmodified-target replay only;
- compare canonical versus capture-only and capture-only versus replay for target rows, trades, fees, slippage, spread, realized exposure, sleeve equity, fold fund NAV, and stitched NAV;
- require two independent runs with deterministic artifact identities;
- write an equivalence manifest and artifact SHA-256 manifest;
- fail closed before any counterfactual generation if any mismatch occurs;
- report exact local command output and artifact identities;
- return to this board for a separate development-execution decision.

Not authorized:

- generating static, lagged, or block-permuted controls;
- calculating Campaign #52 performance metrics, bootstrap inference, multiplicity, rankings, or support decisions;
- development or validation outcome comparisons;
- changing Core logic, source data, weights, thresholds, costs, folds, orders, or execution semantics;
- paper trading, live execution, or runtime modification.

## Stage separation

1. Planning — completed.
2. Feasibility — completed.
3. Family selection — completed.
4. Statistical specification — completed.
5. Source/calendar preflight — PASS.
6. Capture/replay implementation and synthetic validation — PASS.
7. Governed-source capture/replay equivalence run — **authorized next**.
8. Development/validation execution — not authorized.
9. Prospective confirmation — not authorized.
10. Economic, paper, or runtime action — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
