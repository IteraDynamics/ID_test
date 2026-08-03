# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Status:** DEVELOPMENT/VALIDATION EXECUTION GO — amended support gates passed all non-outcome validation; execute exactly two deterministic 2018–2024 replays through the amended governed entry point only. Every 2025 row, holdout confirmation, economic testing, paper trading, and runtime/strategy work remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

## Governed design

- Base statistical specification: commit `36dd499d00740062f10c1c070896f740f55f6808`
- Frozen source universe: commit `f32cac981bf55d0b1799949988df70e5546394e5`
- Execution procedure: commit `16b00d8e5f33a1636a65cb6a3885b19562726551`
- Support-gate amendment: commit `18ff04022fac611c4c2c6136132afa57ee8ad30e`
- Amended implementation constants: commit `29b38116eccb2802756c622ac260eb0908492ad2`
- Fresh execution GO: commit `07276cc5831de016ebb55259c3c8154ec10cde86`
- Amended execution entry point: commit `71a77cf4969fbc61a56db711c1e8ef781d5e1c5f`
- Amended-entrypoint metadata test: commit `f864571d26bf235332afe46e5b0b43388e9078ef`

Research family: equity breadth deterioration and recovery.

Targets: SPY and QQQ.

Breadth members: RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, and XLY.

Candidate inventory: exactly 24 candidates from four predictors, two targets, and 5-, 20-, and 60-session forward-return horizons.

Intervals:

- development: `2018-01-02` through `2022-12-30`
- validation: `2023-01-03` through `2024-12-31`
- untouched holdout: `2025-01-02` through `2025-12-30`

Amended development total-support gates:

- 5 sessions: 180
- 20 sessions: 50
- 60 sessions: 16

All other frozen methods and gates remain unchanged.

## Validation evidence

- Synthetic and runner tests: `14 passed in 0.13s`
- Source-only preflight: `PASS`; candidate count 24; confirmation disabled; no predictors or outcomes generated
- Date-only feasibility preflight: `PASS`; no impossible gates; no prices, predictors, outcomes, or holdout loaded
- Maximum/minimum anchors: development 207/180, 51/50, 17/16; validation 100/80, 25/22, 8/8 for 5/20/60 sessions

No real Campaign #50 predictor, return, coefficient, p-value, ranking, validation result, shortlist result, or 2025 observation informed the amendment or this execution GO.

## Current authorization

**Decision:** GO to execute exactly two deterministic development/validation replays using:

`scripts.run_campaign50_development_validation_amended`

Authorized now:

- rerun the complete test set and both non-outcome preflights;
- verify both governed output directories do not exist;
- execute run 1 and run 2 through the amended entry point;
- generate development/validation predictors, forward returns, coefficients, p-values, Holm adjustments, deterministic statuses, and shortlist only for 2018–2024;
- write exactly six canonical artifacts per replay;
- verify exact file-set, byte-length, and SHA-256 replay identity;
- inspect and commit one canonical result set and frozen shortlist;
- update this board and return to HOLD.

Not authorized:

- use of the superseded unamended execution entry point for canonical execution;
- loading any 2025 row analytically;
- holdout confirmation;
- changing any method in response to results;
- economic testing, Core v1 comparison, paper trading, or any runtime/strategy/order/NAV/exposure change.

## Immediate sequence

1. Pull this board and amended entry point.
2. Run all 15 Campaign #50 tests.
3. Rerun source-only and date-only preflights.
4. Verify run-1 and run-2 directories do not exist.
5. Execute amended run 1.
6. Execute amended run 2.
7. Verify byte-identical replay across all six files.
8. Return results for governed review.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.

## Campaign #48 completion

Campaign #48 is complete under closure `77c1ae8c70de7a16cca847aeb1a4cb2eea638007` and canonical publication `fd7ee01`. It authorized no runtime or strategy change.
