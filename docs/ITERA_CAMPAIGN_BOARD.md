# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes unless explicitly stated.

## Active campaign

**Campaign:** Campaign #51 — Conditional Directional Value of Supported BTC Movement States

**Status:** PLANNING OPEN — source-and-variable inventory documented; timestamp-only source feasibility validation authorized next. Campaign #51 forward outcomes, model fitting, family selection, holdout analysis, economic testing, paper trading, and runtime/strategy work remain prohibited.

**Branch:** `agent/campaign-50-holdout-first-alpha-research-planning`

**Repository:** `IteraDynamics/ID_test`

## Objective

> Determine whether BTC volatility and drawdown states already supported by Campaign #48 identify conditions under which a separately defined, pre-existing directional variable has materially different forward directional value.

Campaign #51 does not ask volatility or drawdown to predict direction unconditionally. It asks whether supported movement states condition the value of independently defined directional information.

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

## Campaign #51 planning records

- planning charter: `docs/research/CAMPAIGN_51_CONDITIONAL_DIRECTIONAL_VALUE_PLANNING_CHARTER.md`; commit `59359493787dcac855063debbda8a76895a55378`
- source-and-variable feasibility inventory: `docs/research/CAMPAIGN_51_SOURCE_VARIABLE_FEASIBILITY_INVENTORY.md`; commit `5bdef3783975902516bac49ca23b00b023d108f9`
- timestamp-only feasibility preflight: `scripts/preflight_campaign51_source_variable_feasibility.py`; commit `d6348422f03529f065abe1d096086c01c30ded9d`
- preflight helper tests: `tests/test_campaign51_source_variable_feasibility.py`; commit `6aae3b7d83708b8281eafd0efa056b1d104c366b`

## Governed source

The inventory uses the existing Campaign #48 hourly BTC source only:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- rows: `70,069`
- coverage: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- exact governed missing timestamps: 36 under Campaign #48 amendment `d9fc7e7103a5033a9dbbe06b7abf93aea27d863b`

No interpolation, fill, resampling, matching, shifting, synthetic bars, or source repair is permitted.

## Inventory finding

Existing transparent directional variables:

- 24-hour signed log return;
- 72-hour signed log return;
- 168-hour signed log return;
- distance from the 168-hour mean;
- position within the 168-hour range.

Campaign #48-supported movement-state variables:

- trailing 24-hour realized volatility;
- trailing 168-hour realized volatility;
- drawdown from the trailing 168-hour high.

The inventory recommends, but does not yet select, a narrow 12-candidate family:

- directional variables: 24-hour and 168-hour signed return;
- conditioning states: 24-hour realized volatility and 168-hour drawdown;
- horizons: 24, 72, and 168 hours;
- candidate effect: continuous directional-variable × movement-state interaction;
- count: `2 × 2 × 3 = 12`.

The 72-hour return, 168-hour realized volatility, and price-location variables remain documented alternatives. They are excluded from the initial recommendation to limit nested-variable duplication and multiplicity, not because of Campaign #51 outcomes.

## Proposed feasibility intervals

For timestamp-only review only, not yet frozen:

- development: `2018-01-01 00:00:00` through `2022-12-31 23:00:00`
- validation: `2023-01-01 00:00:00` through `2024-12-31 23:00:00`
- untouched confirmation: `2025-01-01 00:00:00` through `2025-12-31 00:00:00`

The feasibility preflight:

- reads and validates source bytes, schema, and timestamps;
- does not parse or load close values;
- uses the Campaign #48 168-hour anchor grid;
- requires exact trailing timestamp windows;
- checks only whether exact future endpoint timestamps exist inside each proposed stage;
- generates no predictor values, forward returns, models, coefficients, p-values, rankings, or economic results.

## Current authorization

**Decision:** GO to validate the inventory with tests and one real timestamp-only preflight. Family selection remains pending.

Authorized now:

- run `tests/test_campaign51_source_variable_feasibility.py`;
- run `scripts.preflight_campaign51_source_variable_feasibility` against the governed source;
- inspect timestamp-only source identity, gap inventory, coverage, and stage/horizon counts;
- correct defects in the timestamp-only inventory tooling without changing the planning recommendation in response to outcomes;
- update this board with non-outcome feasibility evidence;
- draft a later family-selection memo only after timestamp feasibility passes.

Not authorized:

- parsing close values in the Campaign #51 preflight;
- generating Campaign #51 predictors or forward outcomes;
- selecting or changing variables based on forward performance;
- fitting models or computing coefficients, p-values, rankings, or support decisions;
- analytically loading 2025 holdout values;
- freezing the statistical specification;
- implementing an analytical runner;
- economic-value testing or Core v1 comparison;
- paper trading;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Mandatory stage separation

1. Planning charter — **completed**.
2. Source-and-variable inventory — **documented; timestamp validation pending**.
3. Hypothesis-family selection — **pending**.
4. Frozen statistical specification — **not authorized**.
5. Implementation and synthetic tests — **not authorized**.
6. Development and validation execution — **not authorized**.
7. Untouched historical confirmation — **not authorized**.
8. Economic testing — **not authorized**.
9. Forward paper trading — **not authorized**.
10. Limited-live-capital review — **not authorized**.

## Immediate sequence

1. Pull the inventory, preflight, tests, and board update.
2. Run the focused timestamp-only tests.
3. Run the governed timestamp-only preflight.
4. Record exact stage/horizon counts and all safety flags.
5. Decide whether the recommended 12-candidate family is feasible for a later selection memo.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.
