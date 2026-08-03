# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Classification:** Governed real development/validation execution

**Status:** DEVELOPMENT/VALIDATION EXECUTION GO — amended support gates passed synthetic, source-only, and date-only validation; execute exactly two deterministic 2018–2024 replays only; 2025 holdout access, economic testing, paper trading, runtime work, and strategy work remain prohibited

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Governed records

- Planning charter: `docs/research/CAMPAIGN_50_HOLDOUT_FIRST_ALPHA_RESEARCH.md`; commit `63a9b24aaf13a2baaef21140f1ed6a99e6d39ac1`
- Family selection: `docs/research/CAMPAIGN_50_HYPOTHESIS_FAMILY_SELECTION.md`; commit `bfa0b43a7a281f2a6a6aca19f61bc8078e19b17a`
- Source universe: `docs/research/CAMPAIGN_50_EQUITY_SOURCE_UNIVERSE.md`; commit `f32cac981bf55d0b1799949988df70e5546394e5`
- Base statistical specification: `docs/research/CAMPAIGN_50_EQUITY_BREADTH_STATISTICAL_SPEC.md`; commit `36dd499d00740062f10c1c070896f740f55f6808`
- Execution procedure: `docs/research/CAMPAIGN_50_DEVELOPMENT_VALIDATION_EXECUTION_PROCEDURE.md`; commit `16b00d8e5f33a1636a65cb6a3885b19562726551`
- Structural feasibility finding: `docs/research/CAMPAIGN_50_SUPPORT_GATE_FEASIBILITY_FINDING.md`; commit `ea0ef2380ee6dfb022432a0a1726f7fb57cdb3ea`
- Support-gate amendment: `docs/research/CAMPAIGN_50_SUPPORT_GATE_AMENDMENT.md`; commit `18ff04022fac611c4c2c6136132afa57ee8ad30e`
- Amended feasibility constants: commit `0649f09747b2d90ff9d2cca3e18b94b600443f0e`
- Amended implementation constants: commit `29b38116eccb2802756c622ac260eb0908492ad2`
- Amended support-boundary tests: commit `fb9fa45b0c52ef0aaff40a256abd01d5d4f2bc2a`

The amendment supersedes only the development minimum-total-support values for 20-session and 60-session candidates.

## Frozen research design

Research family: **equity breadth deterioration and recovery**.

Targets: SPY and QQQ.

Breadth members: RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, and XLY.

Candidate inventory:

- four predictors;
- two targets;
- 5-, 20-, and 60-session forward-return horizons;
- exactly 24 candidates.

Intervals:

- development: `2018-01-02` through `2022-12-30`
- validation: `2023-01-03` through `2024-12-31`
- untouched holdout: `2025-01-02` through `2025-12-30`

Every 2025 row remains forbidden during this stage.

Amended development total-support gates:

- 5 sessions: 180
- 20 sessions: 50
- 60 sessions: 16

Validation and holdout total-support gates remain unchanged. Binary event/non-event gates remain unchanged. Predictors, outcomes, horizons, expected signs, OLS/HC3, Holm correction, compatibility rules, and shortlist rules remain unchanged.

## Non-outcome validation evidence after amendment

User-run synthetic tests on Windows / Python 3.14.6:

- `14 passed in 0.13s`

User-run source-only implementation preflight:

- status: `PASS`
- candidate count: `24`
- confirmation enabled: `false`
- predictors generated: `false`
- outcomes generated: `false`

User-run date-only execution-feasibility preflight:

- status: `PASS`
- structurally impossible gates: none
- prices loaded: `false`
- predictors generated: `false`
- outcomes generated: `false`
- holdout loaded: `false`

Maximum stage-contained anchors and frozen minimums:

- development 5: maximum 207; minimum 180
- development 20: maximum 51; minimum 50
- development 60: maximum 17; minimum 16
- validation 5: maximum 100; minimum 80
- validation 20: maximum 25; minimum 22
- validation 60: maximum 8; minimum 8

No real Campaign #50 predictor, forward return, coefficient, p-value, ranking, validation result, shortlist result, or 2025 observation informed the amendment or this GO.

## Current authorization

**Decision:** GO to execute the governed real development/validation runner exactly twice under the frozen procedure.

Authorized now:

- rerun synthetic tests and source-only/date-only preflights immediately before execution;
- verify the two governed output directories do not exist;
- execute `scripts.run_campaign50_development_validation` once into run 1 and once into run 2;
- generate real predictors, forward returns, coefficients, p-values, Holm-adjusted values, deterministic statuses, and shortlist results for development and validation only;
- write exactly the six canonical artifacts per replay;
- compare exact file sets, byte lengths, and SHA-256 identities;
- inspect and commit one canonical result set and the frozen shortlist, including an empty shortlist if no candidate passes;
- update this board with execution evidence and return to HOLD.

Not authorized:

- loading any 2025 row into analytical structures;
- running or enabling holdout confirmation;
- modifying any frozen method in response to results;
- economic-value backtesting or Core v1 comparison;
- paper trading;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes.

## Immediate sequence

1. Pull this execution GO.
2. Verify tests and preflights remain PASS.
3. Verify both replay destinations do not exist.
4. Execute run 1.
5. Execute run 2.
6. Verify byte-identical replay across all six files.
7. Review deterministic development/validation statuses only.
8. Commit one canonical result set and frozen shortlist.
9. Update the board and return to HOLD.
10. Require a separate historical-confirmation GO before any 2025 analytical access.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.

## Campaign #48 completion

Campaign #48 is complete under closure `77c1ae8c70de7a16cca847aeb1a4cb2eea638007` and canonical publication `fd7ee01`. It authorized no runtime or strategy change.
