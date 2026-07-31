# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Classification:** Research planning for an immediately testable alpha-development pipeline

**Status:** PRIMARY FAMILY SELECTED — equity breadth deterioration and recovery; source-universe reconciliation and statistical-specification drafting only; no outcomes, implementation, economic backtests, paper trading, runtime work, or strategy work authorized

**Planning branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

**Planning charter:** `docs/research/CAMPAIGN_50_HOLDOUT_FIRST_ALPHA_RESEARCH.md`

**Planning-charter commit:** `63a9b24aaf13a2baaef21140f1ed6a99e6d39ac1`

**Family-selection memo:** `docs/research/CAMPAIGN_50_HYPOTHESIS_FAMILY_SELECTION.md`

**Family-selection commit:** `bfa0b43a7a281f2a6a6aca19f61bc8078e19b17a`

## Objective

> Identify a narrowly defined research-alpha hypothesis that can be discovered, confirmed on an untouched historical holdout, tested economically, and—only after separate gates—advanced to forward paper trading without waiting for new calendar-time data.

Itera Dynamics is building toward an operating quantitative fund. Campaign #50 therefore prioritizes a credible path from research to historical confirmation, economic testing, paper trading, and a future live track record.

## Process correction from Campaigns #48 and #49

Campaign #48 found 15 promising BTC volatility-state and drawdown associations, but its full 2018–2025 source participated in discovery and selection. No terminal Coinbase holdout remained untouched.

Campaign #49 correctly froze a prospective confirmation design and began accumulating post-2025 Coinbase data. Its locked 52-anchor weekly gate cannot mature until approximately January 2027, potentially later because of missing windows.

Campaign #49 remains valid research, but it is no longer the active alpha-development critical path.

Campaign #50 reserves an untouched historical terminal holdout before candidate outcomes are generated.

## Repository inventory conclusion

The repository contains sufficient research and future execution infrastructure to support an immediate holdout-first program:

- daily and hourly OHLCV source patterns;
- deterministic loaders, validation, resampling, backtesting, costs, turnover, replay, and paper-broker infrastructure;
- existing SPY/QQQ equity-book and Core v1 baselines;
- broad daily ETF files spanning index, size, style, sector, international, bond, gold, and cash-like instruments.

Several obvious families were rejected as the Campaign #50 primary because their 2025 observations or closely related economic mappings already participated in prior work:

- BTC simple price state and volatility;
- BTC/ETH relative strength;
- crash-short and long/short combinations;
- jump risk;
- trend persistence and regime-transition/state research;
- SPY/QQQ own-price trend and defensive-cash mappings.

## Ranked family decision

1. **Equity breadth deterioration and recovery — selected primary.**
2. BTC/ETH hour-of-week continuation and reversal.
3. Cross-asset defensive confirmation state.

The selected family asks whether broad participation across a small frozen equity universe contains incremental information about subsequent SPY and QQQ behavior beyond each index's own trend state.

Reasons for selection:

- plausible market-participation mechanism;
- clear incremental distinction from Core v1 own-price trend logic;
- low expected turnover;
- direct mapping to the existing equity book if later confirmed economically;
- sufficient historical daily support for development, validation, and an immediate 2025 terminal holdout;
- lower holdout-contamination risk than previously researched families.

## Mandatory stage separation

Campaign #50 preserves separate governance gates for:

1. discovery on a frozen development interval;
2. historical confirmation on a mechanically untouched terminal holdout;
3. economic-value testing for statistically confirmed candidates only;
4. forward paper trading for economically confirmed candidates only;
5. later limited-live-capital review after a predetermined paper record.

Passing one stage does not authorize the next.

## Provisional temporal architecture

Subject to exact source-coverage reconciliation before outcomes:

- development: `2018-01-01` through `2022-12-31`;
- validation: `2023-01-01` through `2024-12-31`;
- untouched confirmation holdout: `2025-01-01` through the frozen 2025 source endpoint.

Any adjustment must be recorded before outcomes and must preserve a meaningful terminal holdout.

The 2025 holdout may not be used for universe selection, discovery, transformation selection, threshold selection, feature selection, expected-sign selection, candidate ranking, model selection, or real-outcome debugging.

## Current authorization

**Decision:** GO to reconcile the daily source universe and draft the frozen statistical specification for the selected equity-breadth family only.

Authorized now:

- inventory exact daily source files, providers, manifests, coverage, schemas, hashes, duplicate status, and missing-session inventories;
- define a small economically justified ETF universe without using Campaign #50 outcomes;
- identify assets that fail complete-coverage or source-governance requirements;
- draft the statistical specification freezing source identity, universe, intervals, holdout isolation, predictor formulas, outcomes, horizons, expected signs or two-sided rules, multiplicity, support gates, confirmation rules, deterministic statuses, and output schemas;
- update this board with planning evidence.

Not authorized:

- generating or inspecting Campaign #50 predictor or outcome values;
- accessing newly calculated 2025 holdout outcomes;
- implementing Campaign #50 predictors, outcomes, models, labels, or runners;
- economic-value backtesting or Core v1 comparison;
- paper-trading activation;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization for Campaign #50 candidates;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Immediate sequence

1. Preserve Campaign #49 as a passive prospective confirmation track. **Completed.**
2. Open Campaign #50 planning branch and charter. **Completed: `63a9b24`.**
3. Inventory available sources and reusable infrastructure. **Completed for family selection.**
4. Identify and rank no more than three hypothesis families. **Completed.**
5. Select one primary family. **Completed: equity breadth deterioration and recovery, `bfa0b43`.**
6. Reconcile and freeze the exact daily source universe. **Authorized next.**
7. Draft and freeze the statistical research specification and untouched holdout. **Authorized after source reconciliation.**
8. Record a separate implementation GO. **Not authorized.**
9. Generate discovery outcomes only after implementation and preflight gates. **Not authorized.**
10. Unlock the historical holdout only after shortlist and confirmation rules are frozen. **Not authorized.**
11. Economic testing and paper trading require later separate gates. **Not authorized.**

## Passive campaign

### Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

**Status:** PASSIVE PROSPECTIVE ACCUMULATION — methodology locked; initial post-2025 source published; deterministic source updater validated; no confirmation computation until every locked sample gate is met

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
