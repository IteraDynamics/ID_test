# Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

## Status

**DRAFT GOVERNING SPECIFICATION — SOURCE PROVIDER SELECTED; SOURCE ACQUISITION ONLY.**

No Campaign #49 confirmation outcome may be generated, calculated, viewed, inspected, ranked, or interpreted under this draft.

Campaign #49 is research-only, observation-only, deterministic, replay-safe, chronological, leakage-safe, and fail-closed.

It authorizes no runtime, regime, threshold, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Plain-English question

> Do the volatility-state persistence and drawdown-linked future-volatility associations discovered in Campaign #48 survive an honestly independent, separately frozen confirmation design?

Campaign #49 is not a new discovery sweep. It must not search for better predictors, transformations, horizons, thresholds, interactions, labels, or economic implementations.

## Governed lineage

- Campaign #48 closure: `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`
- Campaign #48 canonical publication: `fd7ee01`

Campaign #48 established 15 supported horizon-specific associations across five scientific groups:

1. trailing 24-hour realized volatility positively associated with future absolute return;
2. trailing 24-hour realized volatility positively associated with future realized volatility;
3. trailing 168-hour realized volatility positively associated with future absolute return;
4. trailing 168-hour realized volatility positively associated with future realized volatility;
5. deeper drawdown from the trailing 168-hour high associated with higher future realized volatility.

Each group was supported at exact 24-hour, 72-hour, and 168-hour horizons. No directional-return association was supported, so Campaign #49 will not reopen directional-return discovery.

## Independent-confirmation principle

The primary confirmation claim must rely only on BTC hourly observations strictly after the Campaign #48 source endpoint:

`2025-12-31 00:00:00`

Historical reuse may be used only for implementation testing, source reconciliation, or explicitly labeled sensitivity analysis. It may not be described as independent confirmation.

## Selected primary source provider

The selected provider is **Coinbase Exchange**, using the spot product:

`BTC-USD`

The selected official endpoint family is:

`https://api.exchange.coinbase.com/products/BTC-USD/candles`

The fixed acquisition granularity is:

`3600` seconds

The repository already contains the deterministic acquisition utility:

`scripts/fetch_coinbase_hourly_history.py`

The existing utility requests Coinbase Exchange candles in bounded chunks, parses the documented response order `[time, low, high, open, close, volume]`, converts timestamps to timezone-naive UTC hourly values, sorts, removes duplicate timestamps deterministically, and writes the exact research schema:

`timestamp,open,high,low,close,volume`

### Provider-specific constraints

Coinbase Exchange documents that:

- one-hour granularity is supported;
- one request may return at most 300 candles;
- larger ranges must be retrieved through multiple bounded requests;
- historical candles may be incomplete;
- intervals with no ticks may have no published candle.

Therefore Coinbase data is acceptable only under exact source reconciliation. Missing timestamps are not repaired, shifted, filled, interpolated, resampled, or synthesized. The full missing-hour inventory must be recorded and frozen for every governed snapshot.

## Prospective source-acquisition protocol

Campaign #49 will use immutable, cumulative snapshots from the same provider, product, endpoint family, schema, timezone convention, and acquisition utility.

### Initial governed snapshot

The first acquisition window is fixed as:

- start: `2026-01-01T00:00:00Z`;
- end: `2026-07-31T13:00:00Z`;
- product: `BTC-USD`;
- granularity: `3600` seconds;
- output schema: `timestamp,open,high,low,close,volume`.

The intended initial local output path is:

`data/btcusd_3600s_2026-01-01_to_2026-07-31.csv`

The snapshot must be acquired once, validated without confirmation outcomes, hashed, and committed with a separate source manifest. Any acquisition warning is evidence to inspect, not permission to repair data.

### Subsequent cumulative snapshots

Later snapshots must:

- begin at the same fixed start timestamp;
- extend only the exact end timestamp;
- use the same Coinbase product and endpoint family;
- use the same one-hour granularity and ordered schema;
- preserve all previously frozen rows byte-for-value after canonical serialization;
- report any historical revision, disappeared candle, added candle inside the prior frozen interval, or changed OHLCV value as a hard reconciliation failure;
- never substitute another exchange or aggregate provider.

A later cumulative snapshot may become the final confirmation source only after its exact identity, bytes, coverage, provenance, and complete missing-hour inventory are frozen before outcomes.

## Current feasibility as of July 31, 2026

Even assuming perfect hourly coverage from January 1 through July 31, 2026, the untouched source is not yet mature enough for the proposed primary 168-hour confirmation gate.

For a 168-hour predictor lookback and non-overlapping 168-hour forward outcomes:

- the first eligible anchor is no earlier than `2026-01-08 00:00:00`;
- the initial snapshot can support at most 29 complete non-overlapping 168-hour anchors;
- the proposed minimum is 52 complete 168-hour anchors.

The 52nd weekly anchor requires source coverage through at least approximately:

`2027-01-07 00:00:00`

Missing windows may push the actual maturity date later.

The minimum gate will not be reduced merely to accelerate the campaign.

## Frozen predictor formulas carried forward

Only three predictors are eligible.

Let `C_t` denote the exact hourly close and `r_u = ln(C_u / C_{u-1h})`.

### P1 — trailing 24-hour realized volatility

`rv_24_t = sqrt(sum(r_u^2))`

using all 24 exact hourly returns with endpoints in `(t-24h, t]`.

### P2 — trailing 168-hour realized volatility

`rv_168_t = sqrt(sum(r_u^2))`

using all 168 exact hourly returns with endpoints in `(t-168h, t]`.

### P3 — drawdown from trailing 168-hour high

Let `high_168_t` be the maximum of the 169 exact hourly closes in `[t-168h, t]`.

`drawdown_168_t = (C_t / high_168_t) - 1`

No additional predictor is authorized.

## Frozen outcome formulas carried forward

For `h` in `{24, 72, 168}`:

### Family M — future absolute return

`forward_return_h = ln(C_{t+h} / C_t)`

`forward_absolute_return_h = abs(forward_return_h)`

### Family V — future realized volatility

`forward_realized_volatility_h = sqrt(sum(r_u^2))`

using all exact hourly returns with endpoints in `(t, t+h]`.

No directional-return family is included.

## Exact candidate inventory

Exactly 15 Campaign #48 supported associations enter confirmation:

1. P1 → M at 24 hours;
2. P1 → M at 72 hours;
3. P1 → M at 168 hours;
4. P1 → V at 24 hours;
5. P1 → V at 72 hours;
6. P1 → V at 168 hours;
7. P2 → M at 24 hours;
8. P2 → M at 72 hours;
9. P2 → M at 168 hours;
10. P2 → V at 24 hours;
11. P2 → V at 72 hours;
12. P2 → V at 168 hours;
13. P3 → V at 24 hours;
14. P3 → V at 72 hours;
15. P3 → V at 168 hours.

No candidate may be added, removed, transformed, replaced, or reprioritized after confirmation outcomes are generated or inspected.

## Proposed anchor construction

For each horizon `h`:

- the anchor origin is the earliest exact timestamp with a complete 168-hour predictor window and complete `h`-hour outcome window;
- scheduled anchors advance by exactly `h` hours;
- an anchor is retained only when every required timestamp exists;
- missing scheduled anchors are not shifted or replaced;
- adjacent outcomes within the same horizon do not overlap.

This design produces one non-overlapping observation per day, three days, and week for the 24-, 72-, and 168-hour horizons respectively.

## Proposed estimator

Each candidate uses OLS with:

- intercept;
- exactly one standardized predictor;
- no regimes;
- no fixed effects;
- no additional controls;
- no interactions;
- HC3 covariance;
- two-sided normal p-value;
- 95% normal confidence interval using `1.959963984540054`.

Predictor standardization uses the complete confirmation sample for the candidate with population standard deviation `ddof=0`. Outcomes are not standardized.

## Expected signs

- P1 → M: positive;
- P1 → V: positive;
- P2 → M: positive;
- P2 → V: positive;
- P3 → V: negative.

A zero, nonfinite, or opposite-sign coefficient fails directional replication.

## Proposed multiplicity and decision rule

The 15 candidates form one confirmatory family under Holm family-wise error control at alpha `0.05`.

A horizon-specific association confirms only when:

1. its coefficient has the expected sign;
2. its two-sided Holm-adjusted p-value is `<= 0.05`;
3. it passes all source, sample, variance, rank, and estimator gates;
4. it passes the frozen effect-size compatibility rule.

A scientific group confirms only when at least two of its three horizons confirm and the remaining horizon has the expected sign.

The campaign result is positive only when at least three of five groups confirm, including at least one future-absolute-return group and one future-realized-volatility group.

## Proposed minimum sample gates

- at least 180 candidate-complete 24-hour anchors;
- at least 90 candidate-complete 72-hour anchors;
- at least 52 candidate-complete 168-hour anchors.

Because every group includes all three horizons, primary confirmation may not run until the 168-hour gate is met.

## Effect-size compatibility

The exact compatibility interval remains unresolved and must be frozen using Campaign #48 canonical results only, before Campaign #49 outcomes.

The final rule must require:

- expected sign replication;
- finite nonzero confirmation estimate;
- compatibility with a prespecified Campaign #48 reference interval;
- explicit caution for materially larger confirmation effects.

## Rankability and deterministic statuses

A candidate is rankable only when the source reconciles exactly, minimum support is met, all values are finite, predictor variance is positive, the design is full rank, coefficient and HC3 standard error are valid, and the p-value is finite.

Every candidate remains visible under one deterministic status:

1. `CONFIRMED_ASSOCIATION`;
2. `MULTIPLICITY_NOT_MET`;
3. `DIRECTION_NOT_REPLICATED`;
4. `EFFECT_COMPATIBILITY_NOT_MET`;
5. `INSUFFICIENT_CONFIRMATION_SUPPORT`;
6. `OUTCOME_OR_PREDICTOR_UNAVAILABLE`;
7. `ZERO_OR_NONFINITE_VARIANCE`;
8. `RANK_DEFICIENT_DESIGN`;
9. `ESTIMATOR_FAILURE`.

Failure precedence must be frozen in the implementation handoff.

## Preflight requirement

Before any confirmation outcome is generated, preflight must verify source identity and provenance, schema, timestamps, complete missing-hour inventory, positive finite closes, candidate and expected-sign inventories, anchor rules, multiplicity, sample gates, and anticipated anchor counts.

Preflight must report:

`confirmation_outcomes_generated:false`

## Replay and immutability

A future implementation must require source hashing before generation, two byte-identical canonical runs, post-generation preflight, and proof that governed source bytes remained unchanged.

## Interpretation boundary

Campaign #49 can confirm a statistical association only. It cannot establish alpha, economic value, transaction-cost robustness, portfolio improvement, sizing, timing, Core v1 superiority, or production readiness.

Only a successfully confirmed result may enter a later separately frozen economic-value campaign.

## Current authorization boundary

Authorized now:

- acquire the fixed initial Coinbase BTC-USD snapshot;
- validate only source identity, schema, timestamps, OHLCV validity, exact missing-hour inventory, and deterministic serialization;
- create a source manifest containing provenance, command, endpoint family, product, fixed start/end, SHA-256, byte count, row count, schema, endpoints, timezone, and missing timestamps;
- commit only the source CSV and source manifest on the governance branch after validation;
- continue refining this specification using Campaign #48 results only.

Not authorized:

- calculating any Campaign #49 predictor or outcome;
- constructing confirmation anchors;
- fitting or inspecting any Campaign #49 candidate;
- implementation module, confirmation runner, result artifact, economic test, Core v1 comparison, runtime, or strategy work.

## Remaining design-review decisions

1. Validate and freeze the initial Coinbase source snapshot.
2. Confirm horizon-specific non-overlapping grids.
3. Confirm Holm correction across all 15 candidates.
4. Confirm the two-of-three group rule.
5. Confirm the three-of-five campaign rule.
6. Freeze minimum sample gates without outcome inspection.
7. Freeze effect-size compatibility intervals from Campaign #48 only.
8. Freeze exact output schemas and status precedence in a later implementation handoff.
