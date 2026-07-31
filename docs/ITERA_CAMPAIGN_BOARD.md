# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Classification:** Research implementation for an immediately testable alpha-development pipeline

**Status:** IMPLEMENTATION GO — build and validate discovery/validation machinery only; 2025 holdout access, real outcome execution, economic backtests, paper trading, runtime work, and strategy work remain prohibited

**Planning and implementation branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

**Planning charter:** `docs/research/CAMPAIGN_50_HOLDOUT_FIRST_ALPHA_RESEARCH.md`

**Planning-charter commit:** `63a9b24aaf13a2baaef21140f1ed6a99e6d39ac1`

**Family-selection memo:** `docs/research/CAMPAIGN_50_HYPOTHESIS_FAMILY_SELECTION.md`

**Family-selection commit:** `bfa0b43a7a281f2a6a6aca19f61bc8078e19b17a`

**Frozen source universe:** `docs/research/CAMPAIGN_50_EQUITY_SOURCE_UNIVERSE.md`

**Source-universe commit:** `f32cac981bf55d0b1799949988df70e5546394e5`

**Source validator tolerance commit:** `99976db643da2cd8b056998eb0487ae963a39e87`

**Frozen statistical specification:** `docs/research/CAMPAIGN_50_EQUITY_BREADTH_STATISTICAL_SPEC.md`

**Statistical-specification commit:** `36dd499d00740062f10c1c070896f740f55f6808`

## Objective

> Identify a narrowly defined research-alpha hypothesis that can be discovered, confirmed on an untouched historical holdout, tested economically, and—only after separate gates—advanced to forward paper trading without waiting for new calendar-time data.

Itera Dynamics is building toward an operating quantitative fund. Campaign #50 therefore prioritizes a credible path from research to historical confirmation, economic testing, paper trading, and a future live track record.

## Selected research family

**Equity breadth deterioration and recovery.**

The frozen research question is whether broad participation across a fixed domestic equity ETF universe contains incremental information about subsequent SPY and QQQ returns beyond each target index's own price-trend state.

The governed universe contains:

- targets: SPY and QQQ;
- breadth members: RSP, MDY, IWM, IWD, IWF, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, and XLY.

The selected family is distinct from Core v1 own-price trend logic, has low expected turnover if later mapped economically, and can be confirmed on an untouched 2025 terminal holdout.

## Source reconciliation evidence

The exact 16 source files and SHA-256 identities are frozen in the source-universe annex.

Source-only reconciliation established:

- exact hashes matched;
- exact ordered OHLCV schemas matched;
- unique strictly increasing sessions;
- all 16 files share the complete 2,010-session SPY/QQQ target calendar;
- development, validation, and holdout intervals require no dropped common sessions;
- no Campaign #50 predictor or outcome was generated during inventory or reconciliation.

The validator permits only deterministic machine-scale adjusted-price rounding tolerance. It does not repair or rewrite source values.

## Frozen temporal architecture

- development: `2018-01-02` through `2022-12-30`;
- validation: `2023-01-03` through `2024-12-31`;
- untouched confirmation holdout: `2025-01-02` through `2025-12-30`.

The 2025 holdout may not be loaded by discovery or validation code. It may not be used for debugging, feature selection, transformation selection, threshold selection, expected-sign selection, candidate ranking, model choice, or decision-rule modification.

## Frozen statistical design summary

The specification freezes:

- four predictors: breadth level, 20-session breadth change, narrow-strength divergence, and broad recovery;
- two targets: SPY and QQQ;
- three forward-return horizons: 5, 20, and 60 sessions;
- exactly 24 candidates;
- horizon-specific non-overlapping anchor grids;
- OLS with HC3 covariance;
- two-sided raw p-values and frozen expected-sign checks;
- Holm correction across all 24 candidates separately within development, validation, and holdout;
- deterministic minimum-support, compatibility, shortlist, confirmation, and family-level decision rules;
- canonical output schemas and deterministic failure precedence;
- mechanical holdout isolation and separate discovery/validation and confirmation entry points.

No candidate, predictor, target, horizon, transformation, control, interaction, or outcome may be added without a new pre-outcome governance decision.

## Mandatory stage separation

Campaign #50 preserves separate governance gates for:

1. implementation and synthetic/preflight validation;
2. development and validation execution;
3. historical confirmation on the mechanically untouched terminal holdout;
4. economic-value testing for statistically confirmed candidates only;
5. forward paper trading for economically confirmed candidates only;
6. later limited-live-capital review after a predetermined paper record.

Passing one stage does not authorize the next.

## Current authorization

**Decision:** GO to implement and validate the Campaign #50 discovery/validation machinery under the frozen statistical specification.

Authorized now:

- implement deterministic source loading for the 16 exact frozen source identities;
- implement source, schema, ordering, session-calendar, interval, candidate-inventory, and clean-output preflight checks;
- implement the four frozen predictor formulas and three frozen forward-return horizons;
- implement deterministic non-overlapping anchor construction for development and validation only;
- implement the frozen OLS, HC3, raw p-value, confidence interval, standardization, Holm correction, support-gate, sign, magnitude-compatibility, and shortlist logic;
- implement canonical discovery/validation outputs exactly as specified;
- implement separate discovery/validation and confirmation entry-point boundaries;
- implement a fail-closed rejection of any discovery/validation source row dated after `2024-12-31` before analytical construction;
- create synthetic and fixture-based tests for formulas, anchoring, support gates, statistics, multiplicity, deterministic statuses, canonical serialization, replay identity, and holdout-access rejection;
- run source-only preflight against the real frozen files, provided no predictor or outcome is constructed;
- update this board with implementation and validation evidence.

Not authorized:

- running the discovery/validation machinery against real prices to generate predictor values, forward returns, coefficients, p-values, rankings, validation results, or shortlist outcomes;
- loading any 2025 source row into discovery/validation analytical structures;
- implementing or running the real holdout confirmation path beyond a fail-closed boundary stub;
- accessing newly calculated 2025 holdout outcomes;
- economic-value backtesting or Core v1 comparison;
- paper-trading activation;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization for Campaign #50 candidates;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Required implementation properties

Implementation must remain:

- deterministic;
- replay-safe;
- observation-only;
- chronological and leakage-safe;
- fail-closed;
- isolated from runtime and production modules;
- incapable of silently repairing, substituting, interpolating, forward-filling, backward-filling, or resampling source data.

The discovery/validation entry point must reject post-2024 rows before predictor or outcome construction. The confirmation entry point must remain unusable without a later board-recorded confirmation GO, a committed shortlist, a committed discovery/validation manifest, and exact source identities.

## Immediate sequence

1. Preserve Campaign #49 as a passive prospective confirmation track. **Completed.**
2. Open Campaign #50 planning branch and charter. **Completed: `63a9b24`.**
3. Inventory available sources and reusable infrastructure. **Completed.**
4. Identify and rank no more than three hypothesis families. **Completed.**
5. Select one primary family. **Completed: `bfa0b43`.**
6. Reconcile and freeze the exact daily source universe. **Completed: `f32cac9`; 2,010 common sessions validated.**
7. Freeze the statistical research specification and untouched holdout. **Completed: `36dd499`.**
8. Record a separate implementation GO. **Completed by this board decision.**
9. Implement discovery/validation machinery and synthetic tests. **Authorized next.**
10. Validate implementation and source-only preflight. **Pending.**
11. Record a separate real development/validation execution GO. **Not authorized.**
12. Freeze and commit the shortlist before any holdout execution GO. **Not authorized.**
13. Economic testing and paper trading require later separate gates. **Not authorized.**

## Passive campaign

### Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

**Status:** PASSIVE PROSPECTIVE ACCUMULATION — methodology locked; initial post-2025 Coinbase source published; deterministic source updater validated; no confirmation computation until every locked sample gate is met

**Governance branch:** `agent/campaign-49-btc-volatility-state-confirmation-governance`

**Method lock:** `9203b6f20983b8c168182e6bc58135f4f7d5913c`

**Source updater:** `57c70731309300791b12203011b84caf28b502d9`

**Validation evidence:** `12 passed in 0.61s`; module entry point verified

## Campaign #48 completion record

**Campaign:** Campaign #48 — Simple BTC Price-State Predictive Baselines

**Final status:** COMPLETE — 15 supported research associations under the frozen discovery design

**Closure:** `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Canonical publication:** `fd7ee01`

Campaign #48 found reproducible association between recent BTC volatility/drawdown information and future movement magnitude/volatility, but not direction. It authorized no runtime or strategy change.
