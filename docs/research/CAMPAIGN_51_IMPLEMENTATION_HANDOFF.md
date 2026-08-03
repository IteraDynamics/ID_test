# Campaign #51 Implementation Handoff

## Purpose

Implement the frozen Campaign #51 statistical specification without generating or inspecting real Campaign #51 predictor values, forward outcomes, coefficients, p-values, rankings, shortlist results, confirmation results, or economic results.

Governing statistical specification:

- `docs/research/CAMPAIGN_51_STATISTICAL_SPECIFICATION.md`
- freeze commit: `c2f4770ac84e460a387ad2c341d7a4129034b720`

## Authorized implementation scope

A later implementation GO may modify only:

- one new research-only Campaign #51 analysis module;
- one new source-only implementation preflight script;
- focused synthetic tests for the analysis module and preflight;
- this handoff and the authoritative campaign board for governance updates.

No existing runtime, strategy, signal, regime, classifier, order, execution, portfolio, NAV, exposure, dashboard, or model-training module may be changed.

## Required research module behavior

The research module must expose deterministic, side-effect-free functions for:

- exact source identity and schema validation;
- exact timestamp and governed-gap validation;
- exact-window predictor construction;
- frozen 168-hour anchor construction;
- stage-contained forward outcome construction;
- candidate inventory construction in canonical order;
- development-only means and population-standard-deviation calculation;
- reuse of development transformations in later stages;
- four-column OLS design construction with intercept, both main effects, and interaction;
- HC3 interaction inference;
- full-rank and finite-value validation;
- support-gate evaluation;
- Holm correction with frozen family size 12 and canonical tie-breaking;
- deterministic development, validation, shortlist, and later confirmation classifications;
- canonical CSV and strict JSON serialization helpers.

The module must not execute on import, read files on import, write artifacts on import, call runtime code, or mutate global application state.

## Source-only preflight

The preflight may read and hash the governed source bytes and inspect schema and timestamps. It must not parse or load close values into analytical structures.

It must verify:

- exact path identity supplied by the caller;
- exact SHA-256, byte count, row count, column order, endpoint timestamps, ordering, hourly alignment, and 36-timestamp gap inventory;
- exactly 12 canonical candidate definitions;
- frozen stages, horizons, support gates, model-term count, covariance choice, and multiplicity family size;
- confirmation disabled;
- development/validation execution disabled;
- no predictor or forward-outcome generation;
- no runtime modification.

Its output must explicitly report false for:

- `prices_loaded`;
- `predictors_generated`;
- `forward_outcomes_generated`;
- `models_fitted`;
- `holdout_loaded`;
- `confirmation_enabled`;
- `runtime_modified`.

## Synthetic-test requirements

Focused tests must cover at least:

1. exact candidate count, ordering, and keys;
2. exact predictor and state formulas on synthetic complete hourly data;
3. exact-window failure when any required timestamp is missing;
4. stage-contained outcome endpoint enforcement;
5. development-only standardization and unchanged reuse in validation;
6. interaction formed after standardization;
7. full four-term design including both main effects;
8. HC3 inference against an independently checked synthetic fixture;
9. rank-deficient and zero-variance failure behavior;
10. support gates at and immediately below every frozen boundary;
11. Holm family size 12, ordering, and tie behavior;
12. development classification;
13. validation eligibility, sign, adjusted-p, and 0.25-to-4.00 compatibility boundaries;
14. empty-shortlist behavior;
15. confirmation disabled by default;
16. deterministic canonical serialization;
17. source-only preflight safety flags.

Synthetic tests must not use the governed BTC source or inspect real Campaign #51 outcomes.

## Implementation acceptance gates

Before any real development/validation execution can be considered, all must pass:

- focused synthetic tests;
- source-only preflight against the governed source;
- exact candidate inventory count 12;
- exact frozen support gates and family size;
- no prices, predictors, outcomes, models, or holdout loaded by preflight;
- no modification outside authorized research-only files;
- authoritative board review and a separate execution GO.

## Explicitly prohibited

This handoff does not authorize:

- a real development/validation runner;
- generation or inspection of real Campaign #51 predictors or outcomes;
- model fitting on governed prices;
- analytical loading of 2025 values;
- artifact publication containing real Campaign #51 results;
- economic testing or Core v1 comparison;
- paper trading;
- any runtime or strategy change.
