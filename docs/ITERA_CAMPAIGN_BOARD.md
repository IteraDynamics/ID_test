# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Classification:** Pre-outcome statistical-design correction

**Status:** HOLD — development/validation execution GO suspended after a date-only feasibility preflight proved the frozen development support gates structurally impossible at the 20-session and 60-session horizons; no real prices, predictors, outcomes, coefficients, rankings, validation results, shortlist results, or 2025 observations were generated or loaded

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

Identify a narrowly defined research-alpha hypothesis that can be discovered, confirmed on an untouched historical holdout, tested economically, and—only after separate gates—advanced to forward paper trading.

## Governed records

- Planning charter: `docs/research/CAMPAIGN_50_HOLDOUT_FIRST_ALPHA_RESEARCH.md`; commit `63a9b24aaf13a2baaef21140f1ed6a99e6d39ac1`
- Family selection: `docs/research/CAMPAIGN_50_HYPOTHESIS_FAMILY_SELECTION.md`; commit `bfa0b43a7a281f2a6a6aca19f61bc8078e19b17a`
- Source universe: `docs/research/CAMPAIGN_50_EQUITY_SOURCE_UNIVERSE.md`; commit `f32cac981bf55d0b1799949988df70e5546394e5`
- Statistical specification: `docs/research/CAMPAIGN_50_EQUITY_BREADTH_STATISTICAL_SPEC.md`; commit `36dd499d00740062f10c1c070896f740f55f6808`
- Execution procedure: `docs/research/CAMPAIGN_50_DEVELOPMENT_VALIDATION_EXECUTION_PROCEDURE.md`; commit `16b00d8e5f33a1636a65cb6a3885b19562726551`
- Structural feasibility finding: `docs/research/CAMPAIGN_50_SUPPORT_GATE_FEASIBILITY_FINDING.md`; commit `ea0ef2380ee6dfb022432a0a1726f7fb57cdb3ea`
- Date-only feasibility detail update: commit `bebe83152e335ca9c5ce74af1bb0f0eba6653291`

## Frozen research family

**Equity breadth deterioration and recovery.**

Targets: SPY and QQQ.

Breadth members: RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, and XLY.

Frozen candidate inventory:

- four predictors;
- two targets;
- 5-, 20-, and 60-session forward-return horizons;
- exactly 24 candidates.

## Frozen intervals

- development: `2018-01-02` through `2022-12-30`
- validation: `2023-01-03` through `2024-12-31`
- untouched holdout: `2025-01-02` through `2025-12-30`

Every 2025 row remains forbidden during discovery/validation.

## Validation evidence

User-run tests:

- `14 passed in 0.25s`

User-run date-only feasibility preflight:

- status: `FAIL`
- structurally impossible gates:
  - `development__horizon_20`
  - `development__horizon_60`
- prices loaded: `false`
- predictors generated: `false`
- outcomes generated: `false`
- holdout loaded: `false`

The failure is structural and pre-outcome. It arises from the fixed development interval, 220-session lookback, stage-contained outcomes, and non-overlapping horizon grids. It is not an empirical result.

## Current authorization

**Decision:** HOLD. The prior development/validation execution GO is suspended.

Authorized now:

- rerun the date-only feasibility preflight to record exact maximum anchor counts for every stage and horizon;
- inspect calendar-only feasibility evidence;
- draft a pre-outcome governance amendment using only calendar mechanics and an explicit ex ante support rule;
- update the statistical specification, implementation constants, and tests after that amendment;
- rerun synthetic tests, source-only preflight, and date-only feasibility preflight;
- update this board with non-outcome evidence.

Not authorized:

- running `scripts.run_campaign50_development_validation`;
- generating or inspecting real Campaign #50 predictors, returns, coefficients, p-values, rankings, validation results, or shortlist outcomes;
- loading any 2025 row into analytical structures;
- holdout confirmation;
- changing methods in response to empirical results;
- economic backtesting or Core v1 comparison;
- paper trading;
- runtime, threshold, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes.

## Immediate sequence

1. Pull the HOLD transition and expanded date-only feasibility output.
2. Rerun the date-only feasibility preflight.
3. Record exact maximum anchor counts for all six stage/horizon combinations.
4. Freeze a pre-outcome support-gate amendment based only on those calendar counts and a stated ex ante rule.
5. Align specification, implementation, feasibility checks, and tests.
6. Rerun all non-outcome validation.
7. Require a new board-recorded development/validation execution GO.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.

## Campaign #48 completion

Campaign #48 is complete under closure `77c1ae8c70de7a16cca847aeb1a4cb2eea638007` and canonical publication `fd7ee01`. It authorized no runtime or strategy change.
