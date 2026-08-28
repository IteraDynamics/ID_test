# Campaign #50 — Support-Gate Feasibility Finding

## Status

**PRE-OUTCOME STRUCTURAL FAILURE — no real predictor or outcome was generated.**

The date-only execution-feasibility preflight was run after the development/validation execution GO but before either governed analytical replay.

User-run evidence:

- synthetic and runner tests: `14 passed in 0.25s`;
- date-only feasibility status: `FAIL`;
- structurally impossible gates:
  - `development__horizon_20`;
  - `development__horizon_60`;
- `prices_loaded == false`;
- `predictors_generated == false`;
- `outcomes_generated == false`;
- `holdout_loaded == false`.

## Finding

The frozen development support minimums for the 20-session and 60-session horizons exceed the maximum candidate-complete anchor counts mechanically available under the combination of:

- the fixed development interval `2018-01-02` through `2022-12-30`;
- the frozen 220-session required lookback;
- stage-contained forward outcomes;
- horizon-specific non-overlapping anchors.

This is a design-feasibility defect, not an empirical research result. It was detected using dates only, before loading prices or constructing any Campaign #50 predictor, return, coefficient, p-value, ranking, validation result, or shortlist.

## Governance consequence

The development/validation execution GO must be suspended before any real analytical run.

No replacement support gate may be chosen from predictor values, outcome values, coefficients, p-values, candidate rankings, or validation performance.

The exact date-only maximum anchor counts for every stage and horizon must first be recorded. A pre-outcome governance amendment may then set structurally feasible minimum support gates using only calendar mechanics and a stated ex ante rule.

After amendment:

1. update the statistical specification;
2. update implementation constants and tests;
3. rerun synthetic tests;
4. rerun source-only and date-only feasibility preflights;
5. require a new board-recorded development/validation execution GO.

## Current decision

**HOLD.**

Do not run `scripts.run_campaign50_development_validation`.