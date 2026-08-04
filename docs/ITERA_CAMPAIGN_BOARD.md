# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** SOURCE-PREFLIGHT VALIDATION HOLD — the frozen statistical specification, source-only identity/calendar preflight, and focused synthetic tests are committed. Local test evidence and source-only preflight evidence are required before any capture/replay implementation decision.

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
- source/calendar synthetic tests: `59b8b4297be1df783aef52b537f9fc00730623e5`
- inclusive-calendar coverage correction: `a250323fd816e0a9737822a6c8ea9323d6793645`

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

## Governed source contract

Authorized paths:

- `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/ethusd_3600s_2018-01-01_to_2025-12-31.csv`
- `data/SPY_1D.csv`
- `data/QQQ_1D.csv`
- `data/BIL_1D.csv`
- `data/GLD_1D.csv`

Known BTC identity:

- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- bytes: `4,792,028`
- rows: `70,069`

The source-only preflight must freeze the remaining source hashes, byte counts, row counts, schemas, timestamp coverage, ordering, duplicate counts, cadence/missing-calendar characteristics, stage coverage, lag mapping counts, and 28-day block facts. No substitution, repair, interpolation, fill, or acquisition is permitted.

## Source-only preflight implementation

Script:

- `scripts/preflight_campaign52_sources_calendar.py`

Focused tests:

- `tests/test_campaign52_sources_calendar_preflight.py`

The preflight is limited to file bytes, headers, row counts, and timestamps. It must keep these flags false:

- `prices_parsed`
- `targets_generated`
- `signals_generated`
- `positions_generated`
- `trades_generated`
- `costs_generated`
- `returns_generated`
- `nav_generated`
- `performance_metrics_calculated`
- `capture_replay_implemented`
- `runtime_modified`
- `strategy_modified`
- `weights_modified`

## Current authorization

**Decision:** HOLD pending local focused-test and source-only preflight evidence.

Authorized now:

- pull the committed preflight and tests;
- run `tests/test_campaign52_sources_calendar_preflight.py` only;
- run the source-only preflight against the six exact governed paths;
- inspect only the test output and emitted source/calendar JSON;
- correct preflight or calendar-logic defects without changing the frozen Campaign #52 design;
- update this board with exact evidence;
- consider a separate capture/replay implementation decision only after both checks pass.

Not authorized:

- parsing price or return values for analysis;
- running canonical Core v1 or any counterfactual;
- generating targets, signals, positions, trades, costs, returns, NAVs, or metrics;
- implementing capture/replay or counterfactual execution;
- changing any frozen method or Core setting;
- paper trading, live execution, or runtime modification.

## Mandatory stage separation

1. Planning charter — completed.
2. Reference-artifact/intervention feasibility — completed.
3. Hypothesis-family selection — completed.
4. Frozen statistical specification — completed.
5. Source-only identity/calendar preflight — implementation committed; local evidence pending.
6. Capture/replay implementation and synthetic tests — not authorized.
7. Development/validation execution — not authorized.
8. Prospective confirmation — not authorized.
9. Economic, paper, or runtime action — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
