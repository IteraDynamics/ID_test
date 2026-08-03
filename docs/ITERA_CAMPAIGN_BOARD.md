# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #51 — Conditional Directional Value of Supported BTC Movement States

**Status:** RUNNER VALIDATION HOLD — the focused Campaign #51 synthetic suite was reported PASS; a development/validation execution GO and governed runner are committed. New runner-boundary tests must pass locally before real development/validation execution.

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
- development/validation execution GO: `e9eba6f7141851934fbe6a31b4f5c999493d7ab8`
- governed runner initial commit: `5d3680e59ea3dd463d196f15149cc9a99f627d96`
- governed runner correction: `4fb144de0ddd49dff68ac6b450e35384e49a31c5`
- runner-boundary tests: `5e87611edc352c29ec3bf9cd14c46674df37be96`

The exact pytest count for the earlier focused synthetic suite was not supplied and is not asserted; the suite was reported PASS.

## Governed source

Only this source is authorized:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- rows: `70,069`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- exact governed missing timestamps: `36`

Only `timestamp` and pre-2025 `close` values may enter development/validation calculations. No interpolation, filling, resampling, matching, shifting, synthetic bars, timestamp repair, source substitution, or source acquisition is permitted.

The runner may validate full-source timestamps and bytes, but it must not parse or analytically load any 2025 close value.

## Frozen family and model

- directional variables: trailing 24-hour and 168-hour signed log return;
- conditioning states: trailing 24-hour realized volatility and drawdown from the trailing 168-hour close high;
- horizons: 24, 72, and 168 hours;
- exactly 12 candidates.

For each candidate:

`Y = beta0 + betaD * D_z + betaS * S_z + betaI * (D_z * S_z) + epsilon`

- primary estimand: `betaI`;
- candidate-specific development-only standardization with population standard deviation (`ddof=0`), reused unchanged in validation;
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

## Existing validation evidence

Source-only implementation preflight: `PASS`.

- candidate count: `12`
- model term count: `4`
- covariance: `HC3`
- multiplicity: `Holm`
- family size: `12`
- source identity and exact 36-gap inventory matched
- prices loaded: `false`
- predictors generated: `false`
- forward outcomes generated: `false`
- models fitted: `false`
- development/validation execution enabled: `false`
- holdout loaded: `false`
- confirmation enabled: `false`
- runtime modified: `false`

Focused synthetic suite: reported `PASS`.

## Current authorization

**Decision:** HOLD for local validation of the newly committed governed runner.

Authorized now:

- pull the execution GO, corrected runner, and runner-boundary tests;
- run the focused Campaign #51 core tests together with the runner-boundary tests;
- inspect only the local test result;
- correct runner defects without changing the frozen statistical design;
- after the runner tests pass, execute the governed development/validation runner twice into separate directories;
- compare the five canonical output files for exact file-set and byte identity;
- inspect development/validation results only after both runs complete successfully and replay identity passes.

Not authorized:

- parsing or analytically loading any 2025 close value;
- historical confirmation;
- changing any frozen candidate, formula, interval, support gate, model, covariance, multiplicity, or pass rule;
- economic-value testing or Core v1 comparison;
- paper trading;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Mandatory stage separation

1. Planning charter — completed.
2. Source-and-variable feasibility inventory — completed.
3. Hypothesis-family selection — completed.
4. Frozen statistical specification — completed.
5. Implementation and synthetic tests — completed.
6. Development and validation execution — runner committed; local runner validation pending.
7. Untouched historical confirmation — not authorized.
8. Economic testing — not authorized.
9. Forward paper trading — not authorized.
10. Limited-live-capital review — not authorized.

Passing one stage does not authorize the next.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
