# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

No production or portfolio behavior is authorized unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** CALENDAR-COMPATIBLE BLOCK AMENDMENT AND REPLAY-INPUT CACHING IMPLEMENTED — one focused test gate is required, then the actual 2020-2022 development hypothesis test is authorized immediately.

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

## Frozen design

- Core reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- exactly 20 controls: one static, lags `24h`, `168h`, `672h`, and sixteen deterministic 28-day block permutations
- primary endpoints: annualized geometric return, maximum drawdown magnitude, Calmar
- paired daily log-return inference: deterministic 21-day moving-block bootstrap, 10,000 replications
- Holm adjustment across all 20 controls within development
- no Core logic, weights, thresholds, costs, folds, orders, execution, NAV, or exposure semantics may change

## Calendar-compatible block amendment

The first amended governed run reached real development target transformation and failed closed because actual complete 28-day blocks do not always contain equal row counts for every sleeve.

The authorized correction preserves the 28-day wall-clock design but stratifies complete blocks by the ordered row-count signature across the entire frozen sleeve set. Blocks are permuted only within identical-signature groups using deterministic group seeds. Singleton groups remain fixed. No target row may be truncated, padded, interpolated, filled, duplicated, or moved across folds or stages.

The manifest must disclose every signature, compatible group, mapping, movable/fixed count, and per-sleeve equality check.

## Runtime safeguards and efficiency

- two required independent passes execute concurrently by default;
- each pass prepares the 27 fold/sleeve replay inputs once and reuses them across canonical plus all 20 controls;
- all sleeve-level artifacts remain materialized in both passes for exact hash identity;
- all 20 controls and all 10,000 bootstrap replications remain unchanged;
- progress output reports load, input preparation, transformation, each family, bootstrap controls, and pass completion.

## Prior failed attempts

The governed runner has failed closed three times before any valid development result:

1. static helper received the full verified sleeve mean map while transforming a single stream;
2. UTC-aware imported timestamps met timezone-naive fold boundaries;
3. actual sleeve calendars violated the equal-row-count assumption across all complete 28-day blocks.

None of those attempts completed control replay, metrics, inference, multiplicity, or a Campaign classification. Temporary outputs were removed on failure.

## Current authorization

Run the focused implementation suite:

`python -m pytest tests/test_campaign52_development.py tests/test_campaign52_development_runner.py -q`

If and only if it passes, immediately run the actual development hypothesis test with no further authorization step:

`python -m scripts.run_campaign52_development`

The governed run is authorized to:

- verify the governed equivalence artifacts and all six source hashes;
- import only the 27 development target streams;
- generate the amended frozen family of 20 development controls;
- replay canonical plus controls through unchanged execution mechanics;
- calculate the frozen development metrics, bootstrap inference, Holm adjustment, and development decision;
- produce a valid `ADVANCE_TO_VALIDATION_DECISION` or `DEVELOPMENT_NEGATIVE` classification.

Still prohibited:

- opening or analyzing validation target artifacts or validation outcomes;
- changing Core behavior, sources, weights, thresholds, costs, folds, orders, execution, NAV, exposure, runtime, dashboard, or training;
- paper trading, live execution, or economic action.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
