# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Classification:** Research implementation for an immediately testable alpha-development pipeline

**Status:** EXECUTION PROCEDURE PREPARED — implementation and source-only preflight validated; deterministic development/validation execution procedure frozen for review; real outcome execution, 2025 holdout access, economic backtests, paper trading, runtime work, and strategy work remain prohibited

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Identify a narrowly defined research-alpha hypothesis that can be discovered, confirmed on an untouched historical holdout, tested economically, and—only after separate gates—advanced to forward paper trading without waiting for new calendar-time data.

Itera Dynamics is building toward an operating quantitative fund. Campaign #50 therefore prioritizes a credible path from research to historical confirmation, economic testing, paper trading, and a future live track record.

## Governed records

- Planning charter: `docs/research/CAMPAIGN_50_HOLDOUT_FIRST_ALPHA_RESEARCH.md`; commit `63a9b24aaf13a2baaef21140f1ed6a99e6d39ac1`
- Family-selection memo: `docs/research/CAMPAIGN_50_HYPOTHESIS_FAMILY_SELECTION.md`; commit `bfa0b43a7a281f2a6a6aca19f61bc8078e19b17a`
- Frozen source universe: `docs/research/CAMPAIGN_50_EQUITY_SOURCE_UNIVERSE.md`; commit `f32cac981bf55d0b1799949988df70e5546394e5`
- Source validator tolerance: commit `99976db643da2cd8b056998eb0487ae963a39e87`
- Frozen statistical specification: `docs/research/CAMPAIGN_50_EQUITY_BREADTH_STATISTICAL_SPEC.md`; commit `36dd499d00740062f10c1c070896f740f55f6808`
- Implementation GO: commit `030346f6271c89b540d4dea674478529d1a388dd`
- Core research module: commit `562f47b02ef825466be554433232bb78b54ca19a`
- Synthetic test suite: commits `270ab55489fd87ac17d0825edf9b45ffa533718d` and `b3ea0f4cdff64b739b6488681d275c3a976a684f`
- Source-only implementation preflight: commit `5e22c0b28c7bdb74ef7608b72dcfe57a286784d2`
- Development/validation execution procedure: `docs/research/CAMPAIGN_50_DEVELOPMENT_VALIDATION_EXECUTION_PROCEDURE.md`; commit `16b00d8e5f33a1636a65cb6a3885b19562726551`

## Selected research family

**Equity breadth deterioration and recovery.**

The frozen research question is whether broad participation across a fixed domestic equity ETF universe contains incremental information about subsequent SPY and QQQ returns beyond each target index's own price-trend state.

Targets:

- SPY
- QQQ

Breadth members:

- RSP, MDY, IWM, IWD, IWF
- XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY

The family is distinct from Core v1 own-price trend logic, has low expected turnover if later mapped economically, and can be confirmed on an untouched 2025 terminal holdout.

## Source evidence

The exact 16 source files and SHA-256 identities are frozen in the source-universe annex.

Source-only reconciliation established:

- exact hashes and ordered OHLCV schemas matched;
- unique strictly increasing sessions;
- all 16 files share the complete 2,010-session SPY/QQQ target calendar;
- development, validation, and holdout require no dropped common sessions;
- no Campaign #50 predictor or outcome was generated during inventory or reconciliation.

The validator permits only deterministic machine-scale adjusted-price rounding tolerance. It does not repair or rewrite source values.

## Frozen temporal architecture

- development: `2018-01-02` through `2022-12-30`
- validation: `2023-01-03` through `2024-12-31`
- untouched confirmation holdout: `2025-01-02` through `2025-12-30`

The 2025 holdout may not be loaded by discovery or validation code. It may not be used for debugging, feature selection, transformation selection, threshold selection, expected-sign selection, candidate ranking, model choice, or decision-rule modification.

## Frozen statistical design

- four predictors: breadth level, 20-session breadth change, narrow-strength divergence, broad recovery;
- two targets: SPY and QQQ;
- three forward-return horizons: 5, 20, and 60 sessions;
- exactly 24 candidates;
- horizon-specific non-overlapping anchor grids;
- OLS with HC3 covariance;
- two-sided raw p-values and frozen expected-sign checks;
- Holm correction across all 24 candidates separately within development, validation, and holdout;
- deterministic support, compatibility, shortlist, confirmation, and family-level rules;
- canonical output schemas and deterministic failure precedence;
- separate discovery/validation and confirmation boundaries.

No candidate, predictor, target, horizon, transformation, control, interaction, or outcome may be added without a new pre-outcome governance decision.

## Implementation validation evidence

User-run validation on Windows / Python 3.14.6:

- `python -m pytest tests/test_campaign50_equity_breadth.py -q`
- result: `10 passed in 0.16s`

The synthetic suite covers:

- exact stable 24-candidate inventory;
- moving-average and forward-return formulas;
- predictor domains;
- non-overlapping anchors;
- OLS/HC3 behavior;
- deterministic Holm adjustment;
- support gates, expected-sign checks, and magnitude compatibility;
- canonical replay-identical JSON and LF-only CSV serialization;
- fail-closed post-2024 discovery-loader rejection;
- always-disabled confirmation boundary.

User-run real source-only preflight:

- `python -m scripts.preflight_campaign50_equity_breadth --data-root data --output artifacts/campaign50_implementation_preflight.json`
- status: `PASS`
- candidate count: `24`
- confirmation enabled: `false`
- predictors generated: `false`
- outcomes generated: `false`

This evidence validates implementation and source identity only. It contains no real predictor values, forward returns, coefficients, p-values, rankings, validation results, or shortlist outcomes.

## Execution procedure evidence

The proposed execution procedure is frozen in:

- `docs/research/CAMPAIGN_50_DEVELOPMENT_VALIDATION_EXECUTION_PROCEDURE.md`
- commit `16b00d8e5f33a1636a65cb6a3885b19562726551`

It specifies:

- a separate future board-recorded execution GO;
- exact governed branch, specification, source, and interval identities;
- clean, non-existing run-1 and run-2 output directories;
- exactly six canonical files per replay;
- source, schema, ordering, calendar, and post-2024 rejection gates;
- two independent deterministic replay runs;
- exact file-set, byte-length, and SHA-256 replay comparison;
- deterministic manifest requirements without wall-clock or machine-specific fields;
- one canonical result set and one frozen shortlist after replay identity passes;
- return to HOLD before any historical-confirmation GO.

The documented real runner command remains proposed and is not enabled or executed under the current HOLD.

## Mandatory stage separation

Campaign #50 preserves separate governance gates for:

1. implementation and synthetic/preflight validation — **completed**;
2. development and validation execution — **not yet authorized**;
3. historical confirmation on the mechanically untouched terminal holdout — **not authorized**;
4. economic-value testing for statistically confirmed candidates only — **not authorized**;
5. forward paper trading for economically confirmed candidates only — **not authorized**;
6. later limited-live-capital review after a predetermined paper record — **not authorized**.

Passing one stage does not authorize the next.

## Current authorization

**Decision:** HOLD after successful implementation validation and execution-procedure preparation. A separate board-recorded real development/validation execution GO is required before any real Campaign #50 predictor or outcome is generated.

Authorized now:

- inspect implementation, tests, preflight evidence, and the frozen execution procedure;
- add tests that do not use real Campaign #50 outcomes;
- correct implementation defects without changing the frozen design;
- rerun synthetic tests and source-only preflight;
- review the proposed execution procedure and commands;
- update this board with additional non-outcome evidence.

Not authorized:

- running discovery/validation machinery against real prices to generate predictor values, forward returns, coefficients, p-values, rankings, validation results, or shortlist outcomes;
- loading any 2025 row into discovery/validation analytical structures;
- implementing or running real holdout confirmation beyond the fail-closed boundary;
- accessing newly calculated 2025 holdout outcomes;
- economic-value backtesting or Core v1 comparison;
- paper-trading activation;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Immediate sequence

1. Implementation and synthetic tests — **completed**.
2. Real source-only preflight — **completed; PASS**.
3. Review the real development/validation execution procedure and deterministic replay plan — **completed; procedure frozen at `16b00d8`.**
4. Record a separate real development/validation execution GO — **pending**.
5. Implement or enable the governed real runner only under that GO — **not authorized**.
6. Execute development/validation only after that GO — **not authorized**.
7. Commit canonical results and frozen shortlist before any holdout GO — **not authorized**.
8. Historical holdout confirmation requires a later separate gate — **not authorized**.
9. Economic testing and paper trading require later separate gates — **not authorized**.

## Passive campaign

### Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

**Status:** PASSIVE PROSPECTIVE ACCUMULATION — methodology locked; initial post-2025 Coinbase source published; deterministic source updater validated; no confirmation computation until every locked sample gate is met

**Method lock:** `9203b6f20983b8c168182e6bc58135f4f7d5913c`

**Source updater:** `57c70731309300791b12203011b84caf28b502d9`

**Validation evidence:** `12 passed in 0.61s`; module entry point verified

## Campaign #48 completion record

**Final status:** COMPLETE — 15 supported research associations under the frozen discovery design

**Closure:** `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Canonical publication:** `fd7ee01`

Campaign #48 found reproducible association between recent BTC volatility/drawdown information and future movement magnitude/volatility, but not direction. It authorized no runtime or strategy change.
