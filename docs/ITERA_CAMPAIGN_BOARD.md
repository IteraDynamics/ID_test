# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Classification:** Governed real development/validation execution for an immediately testable alpha-development pipeline

**Status:** DEVELOPMENT/VALIDATION EXECUTION GO — enable and run the frozen 2018–2024 discovery/validation procedure with two byte-identical replays only; 2025 holdout access, economic backtests, paper trading, runtime work, and strategy work remain prohibited

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

## Source and interval lock

The exact 16 source files and SHA-256 identities are frozen in the source-universe annex.

Authorized analytical intervals only:

- development: `2018-01-02` through `2022-12-30`
- validation: `2023-01-03` through `2024-12-31`

Untouched and forbidden during this stage:

- holdout: `2025-01-02` through `2025-12-30`
- every source row after `2024-12-31`

The discovery/validation loader must reject a post-2024 row before placing prices into analytical structures.

## Frozen statistical design

- four predictors: breadth level, 20-session breadth change, narrow-strength divergence, broad recovery;
- two targets: SPY and QQQ;
- three forward-return horizons: 5, 20, and 60 sessions;
- exactly 24 candidates;
- horizon-specific non-overlapping anchor grids;
- OLS with HC3 covariance;
- two-sided raw p-values and frozen expected-sign checks;
- Holm correction across all 24 candidates separately within development and validation;
- deterministic support, sign, magnitude-compatibility, and shortlist rules;
- canonical output schemas and deterministic failure precedence.

No candidate, predictor, target, horizon, transformation, control, interaction, outcome, threshold, or method may be added or changed in response to results.

## Validation evidence before execution

User-run synthetic validation:

- `10 passed in 0.16s`

User-run real source-only preflight:

- status: `PASS`
- candidate count: `24`
- confirmation enabled: `false`
- predictors generated: `false`
- outcomes generated: `false`

The deterministic execution procedure is frozen at commit `16b00d8e5f33a1636a65cb6a3885b19562726551`.

## Current authorization

**Decision:** GO to implement or enable the governed real development/validation runner and execute exactly two deterministic replays under the frozen procedure.

Authorized now:

- implement or enable `scripts.run_campaign50_development_validation` without changing the frozen statistical design;
- validate exact source hashes, schemas, ordering, common calendar, branch, output cleanliness, and candidate inventory before analytical construction;
- reject every post-2024 row before placing source values into discovery/validation analytical structures;
- generate real Campaign #50 predictors and forward-return outcomes for development and validation only;
- compute the frozen 24 development and validation candidate results;
- apply the frozen support, OLS/HC3, Holm, expected-sign, magnitude-compatibility, and shortlist rules;
- write exactly the six canonical files per replay specified in the execution procedure;
- run exactly two independent replays in the two governed output directories;
- compare exact file sets, byte lengths, and SHA-256 identities;
- inspect and commit one canonical result set and the frozen shortlist, including an empty shortlist if no candidate passes;
- update this board with execution and replay evidence;
- return to HOLD after the canonical development/validation results are recorded.

Not authorized:

- loading any 2025 row into discovery/validation analytical structures;
- running or enabling real holdout confirmation;
- changing any frozen method in response to development or validation results;
- accessing newly calculated 2025 holdout outcomes;
- economic-value backtesting or Core v1 comparison;
- paper-trading activation;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Mandatory stage separation

1. Implementation and synthetic/preflight validation — **completed**.
2. Development and validation execution — **authorized now**.
3. Historical confirmation on the mechanically untouched terminal holdout — **not authorized**.
4. Economic-value testing — **not authorized**.
5. Forward paper trading — **not authorized**.
6. Limited-live-capital review — **not authorized**.

Passing this stage does not authorize the next.

## Immediate sequence

1. Enable the governed runner under this GO.
2. Rerun synthetic tests and source-only preflight.
3. Verify clean run-1 and run-2 destinations.
4. Execute run 1.
5. Execute run 2.
6. Verify byte-identical replay across all six files.
7. Inspect deterministic development/validation statuses.
8. Commit one canonical result set and frozen shortlist.
9. Update the board and return to HOLD.
10. Require a separate historical-confirmation GO before any 2025 analytical access.

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
