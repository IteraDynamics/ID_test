# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #51 — Conditional Directional Value of Supported BTC Movement States

**Status:** IMPLEMENTATION VALIDATION HOLD — source-only implementation preflight passed; focused synthetic-test evidence remains required before any development/validation execution decision.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

Determine whether BTC volatility and drawdown states already supported by Campaign #48 identify conditions under which recent signed return has materially different forward directional association.

Campaign #51 tests conditional association, not unconditional directional prediction and not a trading strategy.

## Governed lineage

- Campaign #48 closure: `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`
- Campaign #48 canonical publication: `fd7ee01`
- Campaign #50 final closure: `abc38f2cba5cb28603632c4302845e490cb9f4c1`
- planning charter: `59359493787dcac855063debbda8a76895a55378`
- source-and-variable inventory: `5bdef3783975902516bac49ca23b00b023d108f9`
- hypothesis-family selection: `11db395e117343e10ea836231b0903b982e9a674`
- frozen statistical specification: `c2f4770ac84e460a387ad2c341d7a4129034b720`
- implementation handoff: `ecc69384a4951928a88857809b8af54a9c7c1a6d`
- research core: `a0e4857c8582682d0f025085456f56e76e2c2d63`
- source-only implementation preflight: `2a597e0c6f32b3e4d93931ad5e948bbdd4960762`
- focused synthetic tests: `2309356ac0ef11c279d6c2d3a75c78d626a861f8`

## Governed source

Only this source is authorized:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- rows: `70,069`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- exact governed missing timestamps: `36`

Only `timestamp` and `close` may later enter calculations. No interpolation, filling, resampling, matching, shifting, synthetic bars, timestamp repair, source substitution, or source acquisition is permitted.

## Frozen family and model

- directional variables: trailing 24-hour and 168-hour signed log return;
- conditioning states: trailing 24-hour realized volatility and drawdown from the trailing 168-hour close high;
- horizons: 24, 72, and 168 hours;
- exactly 12 candidates.

For each candidate:

`Y = beta0 + betaD * D_z + betaS * S_z + betaI * (D_z * S_z) + epsilon`

- primary estimand: `betaI`;
- candidate-specific development-only standardization with population standard deviation (`ddof=0`), reused unchanged later;
- OLS with HC3 covariance;
- two-sided normal test and 95% confidence interval;
- Holm correction across all 12 candidates separately within each stage.

## Frozen stages and gates

- development: `2018-01-01 00:00:00` through `2022-12-31 23:00:00`
- validation: `2023-01-01 00:00:00` through `2024-12-31 23:00:00`
- untouched confirmation: `2025-01-01 00:00:00` through `2025-12-31 00:00:00`
- anchor origin: `2018-01-08 00:00:00`
- spacing: exactly 168 hours
- exact predictor windows and same-stage future endpoints required
- no stage-boundary crossing

Minimum candidate-complete observations:

| Stage | 24h | 72h | 168h |
|---|---:|---:|---:|
| Development | 220 | 220 | 219 |
| Validation | 90 | 89 | 89 |
| Confirmation | 40 | 39 | 39 |

Development support requires rankability and Holm-adjusted `p <= 0.05`.

Validation support additionally requires prior development support, the same non-zero interaction sign, Holm-adjusted `p <= 0.10`, and an absolute validation/development coefficient ratio in `[0.25, 4.00]`.

Only validation-supported candidates may enter a later confirmation shortlist. An empty shortlist closes Campaign #51 and prohibits 2025 analytical loading.

## Implementation-validation evidence

The governed source-only implementation preflight returned `PASS`.

Identity and contract evidence:

- candidate count: `12`
- model term count: `4`
- covariance: `HC3`
- multiplicity: `Holm`
- multiplicity family size: `12`
- specification commit: `c2f4770ac84e460a387ad2c341d7a4129034b720`
- source SHA-256, byte count, row count, timestamp endpoints, and 36-gap inventory matched the frozen contract
- all 12 canonical candidate keys matched the frozen family
- all stage/horizon support gates matched the frozen specification

Safety flags:

- `prices_loaded`: `false`
- `predictors_generated`: `false`
- `forward_outcomes_generated`: `false`
- `models_fitted`: `false`
- `development_validation_execution_enabled`: `false`
- `holdout_loaded`: `false`
- `confirmation_enabled`: `false`
- `runtime_modified`: `false`

The preflight therefore validates source identity and implementation constants without generating or inspecting governed predictors, outcomes, model results, or 2025 analytical values.

Focused synthetic-test console evidence remains pending.

## Current authorization

**Decision:** HOLD pending focused synthetic-test evidence.

Authorized now:

- run `tests/test_campaign51_conditional_directional.py`;
- inspect only the synthetic test result;
- correct implementation defects without changing the frozen design;
- update this board with the exact test evidence;
- consider a separate development/validation execution decision only after the focused suite passes.

Not authorized:

- a real development/validation runner;
- generation or inspection of real Campaign #51 predictors or forward outcomes;
- fitting Campaign #51 models on governed close values;
- analytically loading any 2025 close;
- changing any frozen method in response to implementation results;
- economic-value testing or Core v1 comparison;
- paper trading;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Mandatory stage separation

1. Planning charter — completed.
2. Source-and-variable feasibility inventory — completed.
3. Hypothesis-family selection — completed.
4. Frozen statistical specification — completed.
5. Implementation and synthetic tests — implementation preflight passed; focused tests pending.
6. Development and validation execution — not authorized.
7. Untouched historical confirmation — not authorized.
8. Economic testing — not authorized.
9. Forward paper trading — not authorized.
10. Limited-live-capital review — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
