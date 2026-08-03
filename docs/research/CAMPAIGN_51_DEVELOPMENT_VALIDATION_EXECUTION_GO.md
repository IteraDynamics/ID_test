# Campaign #51 Development/Validation Execution GO

## Decision

Authorize one deterministic, research-only Campaign #51 development/validation runner and governed execution over 2018 through 2024 only.

This decision follows:

- frozen statistical specification `c2f4770ac84e460a387ad2c341d7a4129034b720`;
- implementation handoff `ecc69384a4951928a88857809b8af54a9c7c1a6d`;
- committed research core `a0e4857c8582682d0f025085456f56e76e2c2d63`;
- source-only implementation preflight `PASS`;
- focused synthetic tests reported `PASS`.

The exact pytest count was not supplied and is not asserted here.

## Authorized execution

The runner may:

- validate the full governed source bytes, schema, timestamp order, endpoints, row count, and exact 36-gap inventory;
- parse `close` values only for timestamps through `2024-12-31 23:00:00`;
- generate the four frozen predictors at exact 168-hour anchors for development and validation;
- generate same-stage forward log-return outcomes at 24, 72, and 168 hours;
- fit the exact frozen four-term interaction model;
- use development-only candidate-specific standardization in both stages;
- apply HC3 inference and Holm correction across all 12 candidates separately within each stage;
- classify development and validation under the frozen rules;
- produce a frozen confirmation shortlist;
- write deterministic canonical artifacts;
- execute twice into separate directories for byte-identity verification.

## Required holdout guard

The runner must validate 2025 timestamps as strings for full-source identity, but it must not parse, convert, inspect, aggregate, or otherwise analytically load any 2025 `close` value.

The runner must report:

- `holdout_loaded: false`;
- `confirmation_enabled: false`;
- `development_validation_execution_enabled: true`;
- `runtime_modified: false`.

If the shortlist is empty, Campaign #51 closes as a valid negative result and no 2025 execution may occur.

If the shortlist is non-empty, 2025 remains untouched until a separate historical-confirmation GO.

## Frozen boundaries

No method changes are authorized. In particular, this GO does not permit changes to:

- candidates;
- formulas;
- intervals;
- anchor origin or spacing;
- exact-window rules;
- support gates;
- standardization;
- model terms;
- covariance;
- multiplicity;
- pass rules;
- coefficient-ratio rules;
- artifact ordering.

## Prohibitions

This GO does not authorize:

- parsing or loading 2025 close values;
- historical confirmation;
- economic-value testing;
- Core v1 comparison;
- paper trading;
- runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes.
