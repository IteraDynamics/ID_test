# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #51 — Conditional Directional Value of Supported BTC Movement States

**Status:** IMPLEMENTATION VALIDATION HOLD — frozen research core, focused synthetic tests, and source-only preflight are committed; local test and preflight evidence are required before any development/validation execution decision. Real Campaign #51 predictor generation, forward outcomes, model fitting on governed values, 2025 analytical access, economic testing, paper trading, and runtime/strategy work remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Determine whether BTC volatility and drawdown states already supported by Campaign #48 identify conditions under which recent signed return has materially different forward directional association.

Campaign #51 tests conditional association, not unconditional directional prediction and not a trading strategy.

## Governed records

- Campaign #48 closure: `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`
- Campaign #48 canonical publication: `fd7ee01`
- Campaign #50 final closure: `docs/research/CAMPAIGN_50_FINAL_CLOSURE.md`; commit `abc38f2cba5cb28603632c4302845e490cb9f4c1`
- Campaign #51 planning charter: `docs/research/CAMPAIGN_51_CONDITIONAL_DIRECTIONAL_VALUE_PLANNING_CHARTER.md`; commit `59359493787dcac855063debbda8a76895a55378`
- source-and-variable inventory: `docs/research/CAMPAIGN_51_SOURCE_VARIABLE_FEASIBILITY_INVENTORY.md`; commit `5bdef3783975902516bac49ca23b00b023d108f9`
- hypothesis-family selection: `docs/research/CAMPAIGN_51_HYPOTHESIS_FAMILY_SELECTION.md`; commit `11db395e117343e10ea836231b0903b982e9a674`
- frozen statistical specification: `docs/research/CAMPAIGN_51_STATISTICAL_SPECIFICATION.md`; commit `c2f4770ac84e460a387ad2c341d7a4129034b720`
- implementation handoff: `docs/research/CAMPAIGN_51_IMPLEMENTATION_HANDOFF.md`; commit `ecc69384a4951928a88857809b8af54a9c7c1a6d`
- research core: `research/campaign51_conditional_directional.py`; commit `a0e4857c8582682d0f025085456f56e76e2c2d63`
- source-only implementation preflight: `scripts/preflight_campaign51_implementation.py`; commit `2a597e0c6f32b3e4d93931ad5e948bbdd4960762`
- focused synthetic tests: `tests/test_campaign51_conditional_directional.py`; commit `2309356ac0ef11c279d6c2d3a75c78d626a861f8`

## Governed source

Only this source is authorized:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- rows: `70,069`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- exact governed missing timestamps: 36 under Campaign #48 amendment `d9fc7e7103a5033a9dbbe06b7abf93aea27d863b`

Only `timestamp` and `close` may later enter Campaign #51 calculations. No interpolation, filling, resampling, matching, shifting, synthetic bars, timestamp repair, source substitution, or source acquisition is permitted.

## Frozen candidate family

- directional variables: trailing 24-hour and 168-hour signed log return;
- conditioning states: trailing 24-hour realized volatility and drawdown from the trailing 168-hour close high;
- horizons: 24, 72, and 168 hours;
- exactly 12 candidates.

## Frozen statistical model

For each candidate:

`Y = beta0 + betaD * D_z + betaS * S_z + betaI * (D_z * S_z) + epsilon`

- outcome: forward BTC log return;
- primary estimand: interaction coefficient `betaI`;
- candidate-specific development-only standardization with population standard deviation (`ddof=0`), reused unchanged later;
- interaction formed after standardization;
- OLS with HC3 covariance;
- two-sided normal test and 95% confidence interval for `betaI`;
- intercept and both main effects required.

## Frozen stages and mechanics

- development: `2018-01-01 00:00:00` through `2022-12-31 23:00:00`
- validation: `2023-01-01 00:00:00` through `2024-12-31 23:00:00`
- untouched confirmation: `2025-01-01 00:00:00` through `2025-12-31 00:00:00`
- anchor origin: `2018-01-08 00:00:00`
- spacing: exactly 168 hours
- exact predictor windows and same-stage future endpoints required
- no stage-boundary crossing

Every 2025 close remains forbidden from analytical loading until a later confirmation GO after a non-empty frozen shortlist.

## Frozen support gates

| Stage | 24h | 72h | 168h |
|---|---:|---:|---:|
| Development | 220 | 220 | 219 |
| Validation | 90 | 89 | 89 |
| Confirmation | 40 | 39 | 39 |

Timestamp-only maxima:

- development: `248, 248, 247`;
- validation: `104, 103, 103`;
- confirmation: `51, 50, 50`.

## Frozen inference and pass rules

- Holm correction across all 12 candidates separately within each stage;
- family size remains 12 when candidates are unrankable;
- canonical order breaks ties;
- interaction sign is not prespecified.

Development support: rankable and Holm-adjusted `p <= 0.05`.

Validation support additionally requires prior development support, same non-zero sign, Holm-adjusted `p <= 0.10`, and absolute validation/development coefficient ratio in `[0.25, 4.00]`.

Only validation-supported candidates enter the frozen confirmation shortlist. An empty shortlist closes Campaign #51 and prohibits 2025 analytical loading.

Confirmation remains unauthorized.

## Existing non-outcome evidence

Timestamp-only feasibility preflight: `PASS`.

- prices loaded: `false`
- predictors generated: `false`
- forward outcomes generated: `false`
- models fitted: `false`
- holdout outcomes loaded: `false`
- runtime modified: `false`

Earlier timestamp-only helper tests were reported PASS; exact count was not supplied.

## Current authorization

**Decision:** HOLD pending local validation of the newly committed implementation.

Authorized now:

- pull the committed research core, tests, and source-only preflight;
- run `tests/test_campaign51_conditional_directional.py`;
- run `scripts.preflight_campaign51_implementation` against the governed source;
- inspect only synthetic-test results and source-only safety evidence;
- correct implementation defects without changing the frozen design;
- update this board with implementation-validation evidence.

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

1. Planning charter — **completed**.
2. Source-and-variable feasibility inventory — **completed**.
3. Hypothesis-family selection — **completed**.
4. Frozen statistical specification — **completed**.
5. Implementation and synthetic tests — **implementation committed; validation pending**.
6. Development and validation execution — **not authorized**.
7. Untouched historical confirmation — **not authorized**.
8. Economic testing — **not authorized**.
9. Forward paper trading — **not authorized**.
10. Limited-live-capital review — **not authorized**.

Passing one stage does not authorize the next.

## Immediate sequence

1. Pull the implementation commits.
2. Run the focused synthetic suite.
3. Run the source-only implementation preflight.
4. Require all analytical-generation, execution, holdout, confirmation, and runtime flags to remain false.
5. Return both console outputs for a separate execution decision.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
