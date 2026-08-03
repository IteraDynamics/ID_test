# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #51 — Conditional Directional Value of Supported BTC Movement States

**Status:** FAMILY SELECTED — planning and non-outcome feasibility complete; frozen statistical specification is the next authorized deliverable. Predictor generation, forward outcomes, analytical implementation, model fitting, holdout access, economic testing, paper trading, and runtime/strategy work remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Determine whether BTC volatility and drawdown states already supported by Campaign #48 identify conditions under which a separately defined recent-return variable has materially different forward directional value.

Campaign #51 does not ask volatility or drawdown to predict direction unconditionally. It asks whether supported movement states condition the directional association of recent signed return.

## Governed antecedents

### Campaign #48

Campaign #48 established 15 supported research associations concentrated in recent realized volatility, future movement magnitude/volatility, and drawdown-linked future volatility. No directional-return candidate was supported.

- closure: `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`
- canonical publication: `fd7ee01`

### Campaign #50

Campaign #50 is permanently closed as a valid governed negative result.

- final closure: `docs/research/CAMPAIGN_50_FINAL_CLOSURE.md`
- closure commit: `abc38f2cba5cb28603632c4302845e490cb9f4c1`
- discovery-supported: `0`
- validation-supported: `0`
- shortlist: empty
- 2025 holdout: untouched

Campaign #50 may not be reopened through post-outcome method changes.

## Campaign #51 governed records

- planning charter: `docs/research/CAMPAIGN_51_CONDITIONAL_DIRECTIONAL_VALUE_PLANNING_CHARTER.md`; commit `59359493787dcac855063debbda8a76895a55378`
- source-and-variable feasibility inventory: `docs/research/CAMPAIGN_51_SOURCE_VARIABLE_FEASIBILITY_INVENTORY.md`; commit `5bdef3783975902516bac49ca23b00b023d108f9`
- timestamp-only feasibility preflight: `scripts/preflight_campaign51_source_variable_feasibility.py`; commit `d6348422f03529f065abe1d096086c01c30ded9d`
- preflight helper tests: `tests/test_campaign51_source_variable_feasibility.py`; commit `6aae3b7d83708b8281eafd0efa056b1d104c366b`
- hypothesis-family selection: `docs/research/CAMPAIGN_51_HYPOTHESIS_FAMILY_SELECTION.md`; commit `11db395e117343e10ea836231b0903b982e9a674`

## Governed source

Only the existing Campaign #48 hourly BTC source is authorized for planning:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- rows: `70,069`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- exact governed missing timestamps: 36 under Campaign #48 amendment `d9fc7e7103a5033a9dbbe06b7abf93aea27d863b`

No interpolation, filling, resampling, matching, shifting, synthetic bars, or source repair is permitted.

## Selected hypothesis family

Directional variables:

- trailing 24-hour signed log return;
- trailing 168-hour signed log return.

Conditioning movement states:

- trailing 24-hour realized volatility;
- drawdown from the trailing 168-hour close high.

Proposed forward horizons:

- 24 hours;
- 72 hours;
- 168 hours.

Candidate effect:

- one continuous directional variable;
- one continuous movement-state variable;
- their interaction;
- later forward directional BTC return outcome, subject to a separately frozen statistical specification.

Candidate count:

- `2 × 2 × 3 = 12`.

The trailing 72-hour return, trailing 168-hour realized volatility, distance from the trailing 168-hour mean, and position within the trailing 168-hour range remain excluded to reduce nested-variable duplication, interpretation overlap, and multiplicity. Their exclusion was not informed by Campaign #51 outcomes.

## Non-outcome feasibility evidence

Timestamp-only source preflight: `PASS`.

Safety flags:

- prices loaded: `false`;
- predictors generated: `false`;
- forward outcomes generated: `false`;
- models fitted: `false`;
- holdout outcomes loaded: `false`;
- runtime modified: `false`.

Stage-contained endpoint anchor counts on the existing 168-hour anchor grid:

- development: 24h `248`, 72h `248`, 168h `247`;
- validation: 24h `104`, 72h `103`, 168h `103`;
- untouched confirmation: 24h `51`, 72h `50`, 168h `50`.

Focused timestamp-only helper tests were reported PASS. The exact pytest count was not supplied and is not asserted by this board.

## Current authorization

**Decision:** GO to draft and freeze a statistical specification only.

Authorized now:

- define the exact Campaign #51 model equation and interpretation of the interaction term;
- define predictor transformations and development-only standardization rules;
- freeze development, validation, and untouched-confirmation intervals;
- freeze anchor spacing, exact-window availability, and stage-contained endpoint rules;
- set ex ante minimum support gates using only calendar/source mechanics;
- select covariance estimator, inferential procedure, multiplicity correction, and pass rules;
- define deterministic artifact and replay requirements;
- inspect no Campaign #51 forward outcomes while doing so;
- update this board with the frozen specification and a separate implementation-authorization decision.

Not authorized:

- generating Campaign #51 predictor values or forward returns;
- fitting Campaign #51 models or computing coefficients, p-values, rankings, or support decisions;
- analytically loading 2025 values;
- implementing an analytical runner before a separate GO;
- economic-value testing or Core v1 comparison;
- paper trading;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Mandatory stage separation

1. Planning charter — **completed**.
2. Source-and-variable feasibility inventory — **completed**.
3. Hypothesis-family selection — **completed**.
4. Frozen statistical specification — **authorized next**.
5. Implementation and synthetic tests — **not authorized**.
6. Development and validation execution — **not authorized**.
7. Untouched historical confirmation — **not authorized**.
8. Economic testing — **not authorized**.
9. Forward paper trading — **not authorized**.
10. Limited-live-capital review — **not authorized**.

Passing one stage does not authorize the next.

## Immediate sequence

1. Draft the exact statistical specification without generating outcomes.
2. Reconcile support gates against the documented calendar-only maxima.
3. Freeze model, inference, multiplicity, shortlist, and replay rules.
4. Return to this board for a separate implementation decision.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
