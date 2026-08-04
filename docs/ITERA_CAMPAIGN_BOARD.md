# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #52 — Core v1 Chronological State Value

**Status:** STATISTICAL SPECIFICATION FROZEN — the method and 20-control family are frozen. Implementation remains on HOLD pending a source-only identity and calendar preflight for all six governed sources. Canonical Core execution, target capture, counterfactual generation, replay implementation, NAV reconstruction, metric calculation, and runtime/strategy changes remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

Determine whether canonical Core v1 derives material value from authentic chronological alignment of its sleeve-level pre-execution signed target exposures, beyond static composition or chronology-destroyed controls replayed through identical execution mechanics.

## Governed records

- planning charter: `docs/research/CAMPAIGN_52_CORE_V1_CHRONOLOGICAL_STATE_VALUE_PLANNING_CHARTER.md`; commit `8ad9f3aae3dc4b36010ef8f723ae1c88bbf7db9d`
- reference/intervention feasibility inventory: `docs/research/CAMPAIGN_52_REFERENCE_INTERVENTION_FEASIBILITY_INVENTORY.md`; commit `a86eba5392e57e936d65c4eb46207cb51c03b309`
- hypothesis-family selection: `docs/research/CAMPAIGN_52_HYPOTHESIS_FAMILY_SELECTION.md`; commit `e2aa9ceafe531e11bea7040fe4309ac9e65b8ab2`
- frozen statistical specification: `docs/research/CAMPAIGN_52_STATISTICAL_SPECIFICATION.md`; commit `14a96b4078eec516570fce0c289baa061398a995`

## Frozen Core reference

- repository reference: `1b556e599fd962469f8b7eace595b15e9d6d6cf6`
- scenario: `baseline_40_35_15_10`
- weights: BTC 1H trend `0.10`, BTC 4H trend `0.10`, ETH 1H trend `0.10`, ETH 4H trend `0.10`, BTC 1H hedge `0.05`, ETH 1H hedge `0.05`, SPY `0.175`, QQQ `0.175`, GLD `0.15`
- no mean-reversion sleeve
- no Core logic, threshold, cost, fold, order, execution, or weight change permitted

## Frozen retrospective stages

Core v1 has already been researched through 2025; Campaign #52 makes no untouched-2025 claim.

- development: `2020-01-01` through `2022-12-31`
- validation: `2023-01-01` through `2025-12-31`
- prospective confirmation: requires future data and a separate later authorization

## Frozen intervention and controls

Primary intervention object: each sleeve's signed target exposure derived from canonical `StrategyIntent` before execution.

Exactly 20 controls:

1. one development-frozen static arithmetic-mean signed target per sleeve;
2. positive wall-clock target lags of `24h`, `168h`, and `672h`;
3. sixteen deterministic stage/fold-contained permutations of complete `28`-day wall-clock blocks.

No negative displacement, wraparound, cross-stage carry, cross-fold carry, order reassignment, position shifting, or NAV rearrangement.

## Frozen primary endpoints

- annualized geometric return
- maximum drawdown magnitude
- Calmar ratio

The inferential series is paired daily log return. A deterministic 21-day moving-block bootstrap with 10,000 replications is frozen. Holm correction applies across all 20 controls separately within each stage.

The exact development, validation, interpretation, multiplicity, replay, and artifact rules are authoritative in `CAMPAIGN_52_STATISTICAL_SPECIFICATION.md`.

## Source contract

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

The ETH, SPY, QQQ, BIL, and GLD SHA-256, bytes, rows, schemas, timestamp coverage, and missing-timestamp inventories are not yet frozen. No substitution, repair, interpolation, fill, or acquisition is permitted.

## Current authorization

**Decision:** GO for a source-only identity and calendar preflight only.

Authorized now:

- implement a research-only preflight that reads file bytes, headers, row counts, and timestamps only;
- compute and report SHA-256, byte count, row count, schema, first/last timestamp, ordering, duplicate counts, and missing-timestamp/calendar characteristics for all six sources;
- verify that development and validation intervals are mechanically coverable;
- verify the 28-day complete-block counts and terminal-block facts using timestamps only;
- verify the `24h`, `168h`, and `672h` displacement calendar mappings using timestamps only;
- keep canonical Core execution, target capture, counterfactual generation, orders, exposures, NAV, metrics, and runtime flags false;
- add focused synthetic tests for timestamp/calendar logic;
- return the evidence for a separate implementation decision.

Not authorized:

- parsing price or return values for analysis;
- running canonical Core v1 or any counterfactual;
- generating targets, signals, positions, trades, costs, returns, NAVs, or metrics;
- implementing capture/replay or the counterfactual engine;
- changing any frozen method or Core setting;
- paper trading, live execution, or runtime modification.

## Mandatory stage separation

1. Planning charter — completed.
2. Reference-artifact and intervention feasibility inventory — completed.
3. Hypothesis-family selection — completed.
4. Frozen statistical specification — completed.
5. Source-only identity/calendar preflight — authorized next.
6. Capture/replay implementation and synthetic tests — not authorized.
7. Development/validation execution — not authorized.
8. Prospective confirmation — not authorized.
9. Economic, paper, or runtime action — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
