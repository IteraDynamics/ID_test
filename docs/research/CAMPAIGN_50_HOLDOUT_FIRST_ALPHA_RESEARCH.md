# Campaign #50 — Holdout-First Alpha Research

## Status

**PLANNING CHARTER — hypothesis-family selection and repository inventory only.**

No Campaign #50 candidate outcome, ranking, economic result, paper-trading result, runtime change, or strategy change is authorized under this charter.

Campaign #50 is intended to restore an immediate path from research to testable alpha while preserving deterministic, replay-safe, chronological, leakage-safe, observation-only, and fail-closed behavior.

## Objective

> Identify a narrowly defined research-alpha hypothesis that can be discovered, confirmed on an untouched historical holdout, tested economically, and—only if every gate passes—advanced to forward paper trading without waiting for additional calendar-time data.

The campaign exists because Campaign #49 produced a promising hypothesis whose clean prospective confirmation sample will not mature until approximately January 2027. Campaign #49 remains scientifically active but is removed from Itera's main alpha-development critical path.

## Mandatory research sequence

Campaign #50 must preserve five separate stages:

1. **Discovery** — screen a frozen candidate family only on a development interval.
2. **Historical confirmation** — test only frozen shortlisted candidates on an untouched terminal holdout that was not used for candidate selection, transformation choice, threshold choice, expected-sign choice, or decision-rule choice.
3. **Economic-value testing** — only statistically confirmed candidates may enter a separately frozen test against the relevant baseline, including explicit cost and turnover assumptions.
4. **Forward paper trading** — only candidates that pass a separately frozen economic gate may enter a live forward paper process.
5. **Limited live-capital review** — requires a later, separate governance decision after a predetermined forward paper record.

Passing one stage does not authorize the next.

## Holdout-first requirement

Before any Campaign #50 research outcome is generated or inspected, the governing specification must freeze:

- exact source identity and hash;
- exact development interval;
- exact validation interval, if used;
- exact untouched terminal confirmation interval;
- candidate family and candidate count;
- formulas and transformations;
- expected signs or two-sided decision rules;
- multiplicity correction;
- minimum support and rankability gates;
- confirmation decision rule;
- prohibited data access during discovery;
- output schemas and deterministic failure precedence.

The untouched holdout must remain mechanically inaccessible to the discovery runner until a separate confirmation GO.

## Initial temporal architecture

The planning default is:

- development: `2018-01-01 00:00:00` through `2022-12-31 23:00:00`;
- validation: `2023-01-01 00:00:00` through `2024-12-31 23:00:00`;
- untouched confirmation holdout: `2025-01-01 00:00:00` through the frozen 2025 source endpoint.

These dates are provisional until exact source coverage and missing-hour effects are inventoried. Any adjustment must occur before outcomes and must preserve a meaningful terminal holdout.

The confirmation holdout may not be used for discovery, tuning, feature selection, threshold selection, model choice, expected-sign selection, or debugging against real outcomes.

## Hypothesis-family selection criteria

The selected family must:

- have a plausible market or behavioral mechanism;
- be computable from source data already present or explicitly authorized;
- be narrow enough to control multiplicity honestly;
- have sufficient observations in each frozen interval;
- produce a potential decision surface that could later be tested economically;
- avoid relying on future information, repaired timestamps, or unstable external labels;
- be implementable without modifying Core v1 or production behavior during research;
- have a realistic path to paper trading if confirmed.

Preference should be given to hypotheses that can add incremental information to Core v1 rather than merely restating its existing logic.

## Repository inventory authorized during planning

Planning may inspect, without generating new research outcomes:

- existing governed BTC, ETH, and SOL hourly sources and manifests;
- existing regime, signal, strategy, feature, and research modules;
- prior campaign specifications and canonical artifacts;
- existing cost, turnover, execution, and paper-trading infrastructure;
- existing unused candidate ideas documented in the repository;
- source coverage and missing-hour inventories;
- whether proposed predictors duplicate Core v1 or earlier campaigns.

Planning must not inspect the 2025 holdout through newly calculated candidate outcomes.

## Candidate-family decision

Campaign #50 must select one primary family before implementation. It must not begin as an open-ended factor zoo.

The family-selection memo must state:

- the economic intuition;
- why it is not already fully represented in Core v1;
- exact source requirements;
- approximate candidate count;
- expected holding horizon;
- likely turnover profile;
- likely role: directional, exposure-gating, risk-state, cross-asset, or execution-aware;
- why the historical holdout can provide a meaningful confirmation test;
- what result would falsify the family.

## Economic-testing boundary

Statistical confirmation alone does not establish alpha.

A later economic specification must freeze before testing:

- signal-to-position mapping;
- baseline comparator;
- transaction costs and slippage;
- rebalance timing;
- exposure and leverage bounds;
- turnover calculation;
- missing-signal behavior;
- performance metrics;
- pass/fail criteria;
- sensitivity limits;
- no-change rules after outcomes.

No runtime, order, strategy, threshold, NAV, exposure, or production change is authorized by Campaign #50 planning or statistical research.

## Paper-trading boundary

Forward paper trading requires a separate campaign or separately frozen stage after economic confirmation. It must include:

- immutable strategy version;
- timestamped signal and order-intent logs;
- deterministic replay;
- cost model;
- operational health checks;
- explicit minimum duration and observation count;
- predefined promotion, extension, and termination rules.

Backtest success alone may not be described as a track record.

## Current planning deliverables

1. inventory the repository for source coverage and reusable research infrastructure;
2. identify no more than three candidate hypothesis families;
3. rank them by mechanism, novelty versus Core v1, holdout feasibility, economic testability, and path to paper trading;
4. select one family;
5. draft a frozen statistical research specification with an untouched 2025 holdout;
6. record a separate implementation GO before coding or outcome generation.

## Prohibited now

- new candidate outcome generation;
- reading or ranking Campaign #50 holdout outcomes;
- implementation of Campaign #50 predictors, labels, or models;
- economic backtests;
- paper-trading activation;
- Core v1 comparison;
- runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes.
