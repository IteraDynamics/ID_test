# Campaign #50 — Equity Breadth Statistical Specification

## Status

**STATISTICAL DESIGN LOCKED — implementation and outcome generation remain separately gated.**

This specification freezes the Campaign #50 statistical research design before any Campaign #50 predictor, outcome, candidate ranking, validation result, or 2025 holdout result is generated or inspected.

It authorizes no economic backtest, Core v1 comparison, paper trading, runtime change, threshold change, strategy change, order generation, exposure change, NAV work, or production behavior.

## Research question

> Does broad participation across a fixed domestic equity ETF universe contain incremental information about subsequent SPY and QQQ returns beyond each target index's own price-trend state?

The economic mechanism is market participation. A cap-weighted index can remain strong while participation narrows beneath the surface. Conversely, broad recovery can precede or reinforce durable index strength.

## Frozen sources

Targets:

- `SPY_1D.csv`
- `QQQ_1D.csv`

Breadth members:

- `RSP_1D.csv`
- `MDY_1D.csv`
- `IWM_1D.csv`
- `IWD_1D.csv`
- `IWF_1D.csv`
- `XLB_1D.csv`
- `XLE_1D.csv`
- `XLF_1D.csv`
- `XLI_1D.csv`
- `XLK_1D.csv`
- `XLP_1D.csv`
- `XLU_1D.csv`
- `XLV_1D.csv`
- `XLY_1D.csv`

The exact SHA-256 identities are governed by `docs/research/CAMPAIGN_50_EQUITY_SOURCE_UNIVERSE.md`.

All files use exact ordered schema:

`timestamp,open,high,low,close,volume`

The source-only reconciliation established:

- exact source hashes matched;
- all 16 files passed schema and source-level validation;
- all 16 files share the complete 2,010-session SPY/QQQ target calendar;
- no predictor or outcome was generated during reconciliation.

No source repair, interpolation, forward fill, backward fill, substitution, or resampling is permitted.

## Frozen intervals

All intervals use the common target session calendar.

- development: `2018-01-02` through `2022-12-30`
- validation: `2023-01-03` through `2024-12-31`
- untouched confirmation holdout: `2025-01-02` through `2025-12-30`

The 2025 holdout may not be loaded by the discovery or validation runner. It may not be used for debugging, feature selection, transformation selection, threshold selection, expected-sign selection, candidate ranking, model choice, or decision-rule modification.

## Price field and timing convention

All calculations use split/dividend-adjusted `close` values exactly as stored.

For session `t`, predictors use only closes at or before `t`.

Forward outcomes begin after predictor formation:

`r_{a,h,t} = close_a[t+h] / close_a[t] - 1`

where `a` is SPY or QQQ and `h` is a frozen forward-session horizon.

No same-session execution or economic mapping is tested in this statistical campaign.

## Frozen trend definitions

For every breadth member `i` and session `t`:

- `ma50_i[t]` = arithmetic mean of member close over sessions `t-49` through `t`
- `above50_i[t]` = `1` if `close_i[t] > ma50_i[t]`, else `0`

For each target `a`:

- `ma200_a[t]` = arithmetic mean of target close over sessions `t-199` through `t`
- `target_above200_a[t]` = `1` if `close_a[t] > ma200_a[t]`, else `0`

Exact equality is classified as not above.

## Frozen breadth predictors

Let `N = 14` breadth members.

### P1 — Breadth level

`breadth50[t] = sum_i(above50_i[t]) / 14`

Continuous predictor in `[0, 1]`.

Expected sign for future target return: positive.

### P2 — Breadth change

`breadth_change20[t] = breadth50[t] - breadth50[t-20]`

Continuous predictor in `[-1, 1]`.

Expected sign for future target return: positive.

### P3 — Narrow-strength divergence

For target `a`:

`narrow_strength_a[t] = 1` when:

- `target_above200_a[t] == 1`, and
- `breadth50[t] <= 0.50`, and
- `breadth_change20[t] < 0`

Otherwise `0`.

Expected sign for future target return: negative.

### P4 — Broad recovery

`broad_recovery[t] = 1` when:

- `breadth50[t] >= 0.70`, and
- `breadth_change20[t] > 0`, and
- `breadth50[t-20] <= 0.50`

Otherwise `0`.

Expected sign for future target return: positive.

Thresholds are frozen before outcome generation and may not be optimized.

## Frozen targets and horizons

Targets:

- SPY
- QQQ

Forward horizons:

- 5 sessions
- 20 sessions
- 60 sessions

Outcome family:

- arithmetic forward close-to-close return

## Frozen candidate inventory

The campaign contains exactly 24 candidates:

- 4 predictors
- 2 targets
- 3 horizons

Candidate key:

`{predictor}__{target}__fwd_return_{h}`

No additional predictor, target, horizon, transformation, interaction, control, or outcome may be added after implementation GO.

## Sampling and overlap

Candidate observations are formed on deterministic non-overlapping anchor grids specific to each horizon.

For interval start session index `s`, the first rankable anchor is the earliest session in that interval having all required lookback history. Subsequent anchors advance by exactly `h` target-calendar sessions.

This avoids overlapping forward-return windows within each candidate.

Rows are candidate-complete only when predictor and forward outcome are finite and fully observed.

## Minimum support gates

Minimum candidate-complete anchors:

- 5-session horizon: 180 in development; 80 in validation; 40 in holdout
- 20-session horizon: 55 in development; 22 in validation; 11 in holdout
- 60-session horizon: 18 in development; 8 in validation; 4 in holdout

Binary predictors additionally require:

- at least 8 event anchors and 8 non-event anchors in development;
- at least 4 event anchors and 4 non-event anchors in validation;
- at least 3 event anchors and 3 non-event anchors in holdout.

A candidate failing a support gate is unrankable for that stage.

## Statistical model

Each candidate is tested separately with one predictor and an intercept:

`future_return = beta_0 + beta_1 * predictor + error`

Continuous predictors are standardized locally within the stage using that stage's candidate-complete observations.

Binary predictors are not standardized.

Inference uses:

- ordinary least squares;
- HC3 heteroskedasticity-consistent covariance;
- two-sided raw p-values;
- 95% confidence intervals;
- coefficient sign evaluated against the frozen expected sign.

No controls, interactions, nonlinear terms, winsorization, trimming, outlier deletion, or alternative covariance estimator are permitted.

## Multiplicity

Holm family-wise correction is applied across all 24 candidates separately within development, validation, and holdout.

No candidate-family subset correction is permitted.

## Discovery and validation rules

A candidate is `DISCOVERY_SUPPORTED` only if:

- rankable in development;
- coefficient has the expected sign;
- development Holm-adjusted p-value `<= 0.05`.

A candidate is `VALIDATION_SUPPORTED` only if:

- it was `DISCOVERY_SUPPORTED`;
- rankable in validation;
- validation coefficient has the same expected sign;
- validation Holm-adjusted p-value `<= 0.10`;
- validation coefficient magnitude is between `0.25x` and `4.0x` the absolute development coefficient.

Only `VALIDATION_SUPPORTED` candidates may enter the frozen confirmation shortlist.

The shortlist and every development/validation result artifact must be committed before any holdout execution GO.

## Holdout confirmation rule

A shortlisted candidate is `CONFIRMED` only if:

- rankable in the holdout;
- coefficient has the frozen expected sign;
- holdout Holm-adjusted p-value `<= 0.10` across the frozen shortlist, with the full 24-candidate family count retained as the multiplicity denominator;
- holdout coefficient magnitude is between `0.25x` and `4.0x` the absolute development coefficient;
- the holdout 95% confidence interval intersects the expected-sign compatibility interval defined by the same magnitude band.

Otherwise it is `NOT_CONFIRMED` or a deterministic unrankable status.

## Family-level decision

A predictor family is supported only if at least one target confirms at two or more horizons, including the 20-session horizon.

Campaign #50 statistical confirmation passes only if:

- at least one predictor family is supported;
- at least one supported family confirms for SPY or QQQ at the 20-session horizon;
- no post-outcome method change occurred.

Statistical confirmation does not authorize economic testing.

## Deterministic failure precedence

Highest precedence first:

1. `SOURCE_IDENTITY_FAILURE`
2. `SOURCE_SCHEMA_FAILURE`
3. `SOURCE_ORDER_FAILURE`
4. `HOLDOUT_ACCESS_VIOLATION`
5. `LOOKBACK_UNAVAILABLE`
6. `INSUFFICIENT_TOTAL_SUPPORT`
7. `INSUFFICIENT_EVENT_SUPPORT`
8. `ZERO_VARIANCE_PREDICTOR`
9. `NONFINITE_MODEL_RESULT`
10. stage-specific unsupported status

A higher-precedence failure suppresses lower-precedence classification.

## Mechanical holdout isolation

Implementation must provide separate entry points and output directories for:

- discovery/validation
- confirmation

The discovery/validation entry point must reject any source row dated after `2024-12-31` before predictor or outcome construction.

The confirmation entry point must require:

- a committed frozen shortlist artifact;
- a committed discovery/validation result manifest;
- exact source hashes;
- a separate board-recorded confirmation GO.

Without all three, it must fail closed before loading 2025 prices into analytical structures.

## Canonical outputs

Discovery/validation stage must produce exactly:

1. `campaign50_preflight.json`
2. `campaign50_candidate_inventory.csv`
3. `campaign50_development_results.csv`
4. `campaign50_validation_results.csv`
5. `campaign50_shortlist.csv`
6. `campaign50_stage_manifest.json`

Confirmation stage must later produce exactly:

7. `campaign50_holdout_results.csv`
8. `campaign50_family_decisions.csv`
9. `campaign50_campaign_decision.json`
10. `campaign50_confirmation_manifest.json`

All outputs must be deterministic, canonical, UTF-8, LF-only, and byte-identical across two replay runs from identical inputs.

## Preflight requirements

Before any outcome generation, preflight must verify:

- all exact source hashes;
- exact schemas;
- strictly increasing unique sessions;
- exact common 2,010-session calendar;
- exact frozen intervals;
- no forbidden holdout access by discovery code;
- exact 24-candidate inventory;
- deterministic anchor counts;
- dependency availability;
- clean output directory.

## Prohibited interpretation

Campaign #50 may establish statistical evidence that breadth contains incremental predictive information.

It may not describe any result as deployable alpha, a strategy, a track record, or an investable system until later economic and forward-paper stages independently pass.
