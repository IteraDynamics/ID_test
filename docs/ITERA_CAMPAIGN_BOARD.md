# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #51 — Conditional Directional Value of Supported BTC Movement States

**Status:** IMPLEMENTATION GO — frozen statistical specification and implementation handoff complete; research-only implementation, focused synthetic tests, and source-only preflight are authorized. Real Campaign #51 predictor generation, forward outcomes, model fitting, development/validation execution, 2025 analytical access, economic testing, paper trading, and runtime/strategy work remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Determine whether BTC volatility and drawdown states already supported by Campaign #48 identify conditions under which recent signed return has materially different forward directional association.

Campaign #51 tests conditional association, not unconditional directional prediction and not a trading strategy.

## Governed antecedents

### Campaign #48

Campaign #48 established 15 supported research associations concentrated in recent realized volatility, future movement magnitude/volatility, and drawdown-linked future volatility. No directional-return candidate was supported.

- closure: `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`
- canonical publication: `fd7ee01`

### Campaign #50

Campaign #50 is permanently closed as a valid governed negative result.

- final closure: `docs/research/CAMPAIGN_50_FINAL_CLOSURE.md`
- closure commit: `abc38f2cba5cb28603632c4302845e490cb9f4c1`
- shortlist: empty
- 2025 holdout: untouched

Campaign #50 may not be reopened through post-outcome method changes.

## Campaign #51 governed records

- planning charter: `docs/research/CAMPAIGN_51_CONDITIONAL_DIRECTIONAL_VALUE_PLANNING_CHARTER.md`; commit `59359493787dcac855063debbda8a76895a55378`
- source-and-variable inventory: `docs/research/CAMPAIGN_51_SOURCE_VARIABLE_FEASIBILITY_INVENTORY.md`; commit `5bdef3783975902516bac49ca23b00b023d108f9`
- timestamp-only feasibility preflight: `scripts/preflight_campaign51_source_variable_feasibility.py`; commit `d6348422f03529f065abe1d096086c01c30ded9d`
- helper tests: `tests/test_campaign51_source_variable_feasibility.py`; commit `6aae3b7d83708b8281eafd0efa056b1d104c366b`
- hypothesis-family selection: `docs/research/CAMPAIGN_51_HYPOTHESIS_FAMILY_SELECTION.md`; commit `11db395e117343e10ea836231b0903b982e9a674`
- frozen statistical specification: `docs/research/CAMPAIGN_51_STATISTICAL_SPECIFICATION.md`; commit `c2f4770ac84e460a387ad2c341d7a4129034b720`
- implementation handoff: `docs/research/CAMPAIGN_51_IMPLEMENTATION_HANDOFF.md`; commit `ecc69384a4951928a88857809b8af54a9c7c1a6d`

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

Directional variables:

- trailing 24-hour signed log return;
- trailing 168-hour signed log return.

Conditioning states:

- trailing 24-hour realized volatility;
- drawdown from the trailing 168-hour close high.

Horizons:

- 24 hours;
- 72 hours;
- 168 hours.

Exactly 12 candidates: `2 × 2 × 3`.

## Frozen statistical model

For each candidate:

`Y = beta0 + betaD * D_z + betaS * S_z + betaI * (D_z * S_z) + epsilon`

- outcome: forward BTC log return;
- primary estimand: interaction coefficient `betaI`;
- standardization: candidate-specific development-only arithmetic mean and population standard deviation (`ddof=0`), reused unchanged in validation and any later confirmation;
- interaction formed after standardization;
- estimator: OLS;
- covariance: HC3;
- test: two-sided normal test of `betaI = 0`;
- 95% normal confidence interval;
- both main effects and intercept required.

No thresholding, quantiling, winsorization, clipping, ranking, sign conversion, nonlinear transformation, residualization, controls, fixed effects, HAC, bootstrap, regularization, or alternative model is permitted.

## Frozen stages and anchor mechanics

- development: `2018-01-01 00:00:00` through `2022-12-31 23:00:00`
- validation: `2023-01-01 00:00:00` through `2024-12-31 23:00:00`
- untouched confirmation: `2025-01-01 00:00:00` through `2025-12-31 00:00:00`
- anchor origin: `2018-01-08 00:00:00`
- anchor spacing: exactly 168 hours
- exact trailing timestamp windows required
- exact future endpoint required inside the same stage
- no stage-boundary crossing

Every 2025 close remains forbidden from analytical loading until a later confirmation GO after a non-empty frozen shortlist.

## Frozen support gates

Minimum candidate-complete observations:

| Stage | 24h | 72h | 168h |
|---|---:|---:|---:|
| Development | 220 | 220 | 219 |
| Validation | 90 | 89 | 89 |
| Confirmation | 40 | 39 | 39 |

Timestamp-only maxima were:

- development: `248, 248, 247`;
- validation: `104, 103, 103`;
- confirmation: `51, 50, 50`.

## Frozen multiplicity and pass rules

- Holm step-down correction across all 12 candidates separately within each stage;
- family size remains 12 even when candidates are unrankable;
- canonical candidate order breaks ties;
- interaction sign is not prespecified.

Development support requires rankability and Holm-adjusted `p <= 0.05`.

Validation support additionally requires:

- prior development support;
- same non-zero interaction sign as development;
- validation Holm-adjusted `p <= 0.10`;
- absolute validation interaction coefficient between `0.25` and `4.00` times the absolute development coefficient, inclusive.

Only validation-supported candidates enter the frozen confirmation shortlist.

An empty shortlist closes Campaign #51 as a valid negative result and prohibits 2025 analytical loading.

Confirmation remains unauthorized. If separately authorized later, support requires the same sign through all three stages, confirmation Holm-adjusted `p <= 0.05`, and an absolute confirmation/development coefficient ratio in `[0.25, 4.00]`.

## Non-outcome feasibility evidence

Timestamp-only source preflight: `PASS`.

- prices loaded: `false`
- predictors generated: `false`
- forward outcomes generated: `false`
- models fitted: `false`
- holdout outcomes loaded: `false`
- runtime modified: `false`

Focused timestamp-only helper tests were reported PASS. The exact pytest count was not supplied and is not asserted.

## Current authorization

**Decision:** GO for research-only implementation, synthetic tests, and source-only preflight.

Authorized now:

- add one new side-effect-free Campaign #51 research analysis module;
- add one new source-only implementation preflight;
- add focused synthetic tests covering formulas, exact windows, standardization, model construction, HC3 inference, support gates, Holm correction, classification, serialization, and safety flags;
- validate source bytes, schema, timestamps, governed gaps, frozen candidate inventory, support gates, and specification identities without parsing close values;
- update this board with implementation evidence;
- correct implementation defects without changing the frozen design.

Not authorized:

- a real development/validation runner;
- generation or inspection of real Campaign #51 predictors or forward outcomes;
- fitting Campaign #51 models on governed source values;
- analytically loading any 2025 close;
- changing any frozen method in response to tests or later results;
- economic-value testing or Core v1 comparison;
- paper trading;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Mandatory stage separation

1. Planning charter — **completed**.
2. Source-and-variable feasibility inventory — **completed**.
3. Hypothesis-family selection — **completed**.
4. Frozen statistical specification — **completed**.
5. Implementation and synthetic tests — **authorized next**.
6. Development and validation execution — **not authorized**.
7. Untouched historical confirmation — **not authorized**.
8. Economic testing — **not authorized**.
9. Forward paper trading — **not authorized**.
10. Limited-live-capital review — **not authorized**.

Passing one stage does not authorize the next.

## Immediate sequence

1. Implement the frozen research module only.
2. Add focused synthetic tests.
3. Add and run the source-only implementation preflight.
4. Require all safety flags to remain false for analytical generation and holdout access.
5. Return implementation evidence to this board for a separate execution decision.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
