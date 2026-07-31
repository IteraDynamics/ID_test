# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #50 — Holdout-First Alpha Research

**Classification:** Research planning for an immediately testable alpha-development pipeline

**Status:** PLANNING GO — repository inventory and hypothesis-family selection only; no Campaign #50 outcomes, implementation, economic backtests, paper trading, runtime work, or strategy work authorized

**Planning branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

**Planning charter:** `docs/research/CAMPAIGN_50_HOLDOUT_FIRST_ALPHA_RESEARCH.md`

**Planning-charter commit:** `63a9b24aaf13a2baaef21140f1ed6a99e6d39ac1`

## Objective

> Identify a narrowly defined research-alpha hypothesis that can be discovered, confirmed on an untouched historical holdout, tested economically, and—only after separate gates—advanced to forward paper trading without waiting for new calendar-time data.

Itera Dynamics is building toward an operating quantitative fund. Campaign #50 therefore prioritizes a credible path from research to historical confirmation, economic testing, paper trading, and a future live track record.

## Process correction from Campaigns #48 and #49

Campaign #48 found 15 promising BTC volatility-state and drawdown associations, but its full 2018–2025 source participated in discovery and selection. No terminal Coinbase holdout remained untouched.

Campaign #49 correctly froze a prospective confirmation design and began accumulating post-2025 Coinbase data. Its locked 52-anchor weekly gate cannot mature until approximately January 2027, potentially later because of missing windows.

Campaign #49 remains valid research, but it is no longer the active alpha-development critical path.

Campaign #50 must reserve an untouched historical terminal holdout before candidate outcomes are generated.

## Mandatory stage separation

Campaign #50 must preserve separate governance gates for:

1. discovery on a frozen development interval;
2. historical confirmation on a mechanically untouched terminal holdout;
3. economic-value testing for statistically confirmed candidates only;
4. forward paper trading for economically confirmed candidates only;
5. later limited-live-capital review after a predetermined paper record.

Passing one stage does not authorize the next.

## Provisional temporal architecture

Subject to source-coverage inventory before outcomes:

- development: `2018-01-01 00:00:00` through `2022-12-31 23:00:00`;
- validation: `2023-01-01 00:00:00` through `2024-12-31 23:00:00`;
- untouched confirmation holdout: `2025-01-01 00:00:00` through the frozen 2025 source endpoint.

Any adjustment must be recorded before outcomes and must preserve a meaningful terminal holdout.

The 2025 holdout may not be used for discovery, transformation selection, threshold selection, feature selection, model selection, expected-sign selection, candidate ranking, or real-outcome debugging.

## Current authorization

**Decision:** GO to Campaign #50 planning and repository inventory only.

Authorized now:

- inspect existing source manifests, coverage, schemas, and missing-hour inventories;
- inspect existing research, regime, signal, feature, strategy, cost, execution, and paper-trading infrastructure;
- inspect prior campaign specifications and canonical artifacts for process and duplication analysis;
- identify no more than three narrowly defined hypothesis families;
- assess each family for mechanism, novelty versus Core v1, sample feasibility, multiplicity burden, expected holding horizon, likely turnover, economic testability, and path to paper trading;
- select one primary family;
- draft a statistical research specification that freezes source, intervals, holdout isolation, candidate inventory, formulas, expected signs or two-sided rules, multiplicity, support gates, decision rules, deterministic statuses, and output schemas;
- update this board with planning evidence.

Not authorized:

- generating or inspecting Campaign #50 candidate outcomes;
- accessing newly calculated 2025 holdout outcomes;
- implementing Campaign #50 predictors, outcomes, models, labels, or runners;
- economic-value backtesting or Core v1 comparison;
- paper-trading activation;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization for Campaign #50 candidates;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Immediate sequence

1. Preserve Campaign #49 as a passive prospective confirmation track. **Completed by Campaign #50 opening decision.**
2. Open Campaign #50 planning branch and charter. **Completed: `63a9b24`.**
3. Inventory available governed sources and reusable research infrastructure. **Authorized next.**
4. Identify and rank no more than three hypothesis families. **Pending.**
5. Select one primary family. **Pending.**
6. Freeze the statistical research specification and untouched holdout. **Not authorized until planning evidence is complete.**
7. Record a separate implementation GO. **Not authorized.**
8. Generate discovery outcomes only after implementation and preflight gates. **Not authorized.**
9. Unlock the historical holdout only after shortlist and confirmation rules are frozen. **Not authorized.**
10. Economic testing and paper trading require later separate gates. **Not authorized.**

## Passive campaign

### Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

**Status:** PASSIVE PROSPECTIVE ACCUMULATION — methodology locked; initial post-2025 Coinbase source published; deterministic source updater validated; no confirmation computation until every locked sample gate is met

**Governance branch:** `agent/campaign-49-btc-volatility-state-confirmation-governance`

**Method lock:** `9203b6f20983b8c168182e6bc58135f4f7d5913c`

**Source updater:** `57c70731309300791b12203011b84caf28b502d9`

**Validation evidence:** `12 passed in 0.61s`; module entry point verified

Campaign #49 retains exactly 15 frozen associations, Coinbase `BTC-USD` as its prospective provider, a fixed post-2025 source protocol, and minimum horizon gates of 180, 90, and 52 candidate-complete anchors. It remains prohibited from generating confirmation outcomes before source maturity and a later execution GO.

## Campaign #48 completion record

**Campaign:** Campaign #48 — Simple BTC Price-State Predictive Baselines

**Final status:** COMPLETE — 15 supported research associations under the frozen discovery design

**Closure:** `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Canonical publication:** `fd7ee01`

Campaign #48 found reproducible association between recent BTC volatility/drawdown information and future movement magnitude/volatility, but not direction. It authorized no runtime or strategy change.

## Historical carryover

Campaign #47 completed historical regime-structure discovery with zero rankable candidates and zero supported associations.

Campaign #45 completed historical regime-transition discovery with zero supported exact ordered-transition associations.

Campaign #46 completed the full historical regime-state source.

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #50 unless separately authorized.
