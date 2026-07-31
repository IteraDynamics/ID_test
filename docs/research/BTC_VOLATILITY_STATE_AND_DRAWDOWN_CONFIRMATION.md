# Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

## Status

**METHODOLOGICAL DESIGN LOCKED — final cumulative source snapshot pending maturity.**

This document fixes the Campaign #49 confirmation method before any Campaign #49 predictor, outcome, anchor, regression, p-value, result, or sensitivity outcome is generated or inspected.

The final cumulative source path, endpoint, bytes, hash, row count, and missing-hour inventory will be frozen in a later source annex only after the minimum untouched-data gate can be met. That later annex may identify the mature source; it may not alter the method below.

Campaign #49 is research-only, observation-only, deterministic, replay-safe, chronological, leakage-safe, and fail-closed. It authorizes no runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Question

> Do the volatility-state persistence and drawdown-linked future-volatility associations discovered in Campaign #48 survive an honestly independent, prospectively untouched confirmation sample?

Campaign #49 is confirmation, not another discovery sweep. It does not search for better predictors, transformations, horizons, thresholds, interactions, labels, controls, or economic implementations.

## Governed lineage

- Campaign #48 closure: `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`
- Campaign #48 canonical publication: `fd7ee01`
- Campaign #48 source endpoint: `2025-12-31 00:00:00`

Only observations strictly after the Campaign #48 endpoint may support the primary confirmation claim. Historical reuse may be used only for synthetic implementation tests or explicitly labeled non-confirmatory reconciliation; it may never be described as independent confirmation.

## Initial prospective source snapshot

The first prospective snapshot was acquired and validated before confirmation computation:

- provider: Coinbase Exchange;
- product: `BTC-USD`;
- endpoint family: `https://api.exchange.coinbase.com/products/BTC-USD/candles`;
- granularity: `3600` seconds;
- acquisition utility: `scripts/fetch_coinbase_hourly_history.py`;
- path: `data/btcusd_3600s_2026-01-01_to_2026-07-31.csv`;
- manifest: `data/btcusd_3600s_2026-01-01_to_2026-07-31.source_manifest.json`;
- first timestamp: `2026-01-01 00:00:00`;
- last timestamp: `2026-07-31 13:00:00`;
- ordered schema: `timestamp,open,high,low,close,volume`;
- rows: `5,073`;
- continuous hourly positions: `5,078`;
- bytes: `350,460`;
- SHA-256: `7af947322b878aee905fb4bd2643f4dec6e9bf0a78551c31a092899c4b8d38ce`;
- validation: `PASS`;
- governed missing timestamps: exactly `2026-05-08 02:00:00` through `2026-05-08 06:00:00` inclusive.

The five missing hours are observations about the provider output, not permission to repair it.

## Cumulative source protocol

Every later snapshot must:

1. use Coinbase Exchange `BTC-USD`, the same endpoint family, one-hour granularity, timezone convention, ordered schema, and acquisition utility;
2. begin at `2026-01-01 00:00:00` and extend only the exact end timestamp;
3. be acquired without predictor or outcome computation;
4. preserve every previously frozen timestamp and OHLCV value after canonical serialization;
5. report any changed value, disappeared candle, or newly appearing candle inside a previously frozen interval as `HISTORICAL_SOURCE_REVISION` and fail closed;
6. record complete provenance, command, endpoints, bytes, SHA-256, row count, schema, timestamp checks, OHLCV checks, and missing-hour inventory;
7. prohibit substitution, interpolation, filling, resampling, nearest-row matching, as-of matching, shifting, synthetic bars, or timestamp repair.

The final confirmation source must be a cumulative snapshot from this protocol and must be frozen before confirmation computation.

## Predictors

Let `C_t` be the exact hourly close and `r_u = ln(C_u / C_{u-1h})`.

Exactly three predictors are authorized:

1. `rv_24_t = sqrt(sum(r_u^2))` over the 24 exact hourly returns ending in `(t-24h, t]`;
2. `rv_168_t = sqrt(sum(r_u^2))` over the 168 exact hourly returns ending in `(t-168h, t]`;
3. `drawdown_168_t = (C_t / max(C_s for s in [t-168h, t])) - 1` using 169 exact closes.

No additional predictor, transformation, threshold, bin, interaction, regime label, or learned feature is authorized.

## Outcomes

For `h` in `{24, 72, 168}`:

- Family M: `abs(ln(C_{t+h} / C_t))`;
- Family V: `sqrt(sum(r_u^2))` over the `h` exact hourly returns ending in `(t, t+h]`.

No directional-return family is included.

## Candidate inventory and expected signs

Exactly 15 candidates enter confirmation:

- trailing 24-hour realized volatility → M at 24, 72, and 168 hours: positive;
- trailing 24-hour realized volatility → V at 24, 72, and 168 hours: positive;
- trailing 168-hour realized volatility → M at 24, 72, and 168 hours: positive;
- trailing 168-hour realized volatility → V at 24, 72, and 168 hours: positive;
- drawdown from the trailing 168-hour high → V at 24, 72, and 168 hours: negative.

The inventory, grouping, horizons, outcomes, and expected signs may not change after this lock.

## Anchor construction

Horizon-specific, non-overlapping anchor grids are fixed.

For each horizon `h`:

1. the scheduled origin is the earliest exact timestamp at or after `2026-01-08 00:00:00` with a complete 168-hour predictor window and complete `h`-hour outcome window;
2. later scheduled anchors advance by exactly `h` hours from that fixed origin;
3. an anchor is retained only when every exact timestamp required by all three predictors and the applicable outcome exists;
4. an unavailable scheduled anchor is omitted and is never shifted or replaced;
5. adjacent retained outcomes within a horizon do not overlap.

The initial May 8 gap may invalidate scheduled windows. It may not move the grid origin or cadence.

## Estimator

Each candidate uses OLS with:

- an intercept;
- exactly one predictor standardized over that candidate's complete confirmation sample using population standard deviation `ddof=0`;
- no regimes, fixed effects, controls, interactions, weights, or regularization;
- HC3 covariance;
- two-sided normal p-value;
- 95% normal confidence interval using `1.959963984540054`.

Outcomes are not standardized.

## Minimum sample gates

A candidate is unrankable unless its horizon has at least:

- 180 candidate-complete anchors at 24 hours;
- 90 candidate-complete anchors at 72 hours;
- 52 candidate-complete anchors at 168 hours.

Primary confirmation may not run until all three horizon gates are met under the final frozen source. The thresholds may not be reduced merely to accelerate the campaign.

As of July 31, 2026, the prospective source is immature. Even perfect coverage could provide at most 29 complete non-overlapping 168-hour anchors. The 52-anchor gate requires coverage into approximately January 2027, and missing windows may delay maturity.

## Multiplicity

All 15 two-sided p-values form one confirmatory family. Holm family-wise error-rate adjustment at alpha `0.05` is fixed.

Holm ordering is ascending raw p-value, with exact candidate ordinal as the deterministic tie-break. Adjusted values are monotonized and capped at `1.0`.

## Effect-size compatibility

Campaign #48 pooled standardized-predictor coefficients are the only discovery references.

For each candidate, define `beta_48` as its Campaign #48 pooled coefficient and define the signed compatibility band as coefficients with:

- the same sign as `beta_48`; and
- absolute magnitude from `0.25 * abs(beta_48)` through `4.0 * abs(beta_48)`, inclusive.

A Campaign #49 estimate passes effect compatibility only when:

1. its point estimate lies inside the signed compatibility band; and
2. its 95% confidence interval intersects that signed compatibility band.

This broad equivalence screen prevents a trivially small or implausibly inflated estimate from being called replication while allowing substantial cross-period variation. It is not an equivalence test and does not replace multiplicity control.

The 15 frozen `beta_48` values are:

| Candidate | `beta_48` |
|---|---:|
| `realized_volatility_trailing_24h__M__24h` | 0.008146156565051988 |
| `realized_volatility_trailing_24h__M__72h` | 0.007993667197349622 |
| `realized_volatility_trailing_24h__M__168h` | 0.011504330470319324 |
| `realized_volatility_trailing_24h__V__24h` | 0.012745964338183912 |
| `realized_volatility_trailing_24h__V__72h` | 0.017333481107299483 |
| `realized_volatility_trailing_24h__V__168h` | 0.025369673184088996 |
| `realized_volatility_trailing_168h__M__24h` | 0.008964081740768496 |
| `realized_volatility_trailing_168h__M__72h` | 0.009151938717643060 |
| `realized_volatility_trailing_168h__M__168h` | 0.009948936391128335 |
| `realized_volatility_trailing_168h__V__24h` | 0.012790454777499053 |
| `realized_volatility_trailing_168h__V__72h` | 0.018186085457430962 |
| `realized_volatility_trailing_168h__V__168h` | 0.025390178989595225 |
| `drawdown_from_high_trailing_168h__V__24h` | -0.010415498081226644 |
| `drawdown_from_high_trailing_168h__V__72h` | -0.014828553880830526 |
| `drawdown_from_high_trailing_168h__V__168h` | -0.020581680747712720 |

## Candidate and group decisions

A horizon-specific candidate is `CONFIRMED_ASSOCIATION` only when it is rankable and all are true:

1. coefficient has the expected sign;
2. Holm-adjusted p-value is `<= 0.05`;
3. effect-size compatibility passes.

The five scientific groups are the five predictor-outcome combinations listed above.

A group confirms only when:

- at least two of its three horizons are `CONFIRMED_ASSOCIATION`; and
- the remaining horizon has a finite nonzero coefficient with the expected sign, even if it misses multiplicity or compatibility.

The campaign-level result is positive only when at least three of five groups confirm, including at least one Family M group and at least one Family V group.

Results not meeting the campaign rule are negative or partial confirmation, not permission to redesign the test.

## Rankability and status precedence

A candidate is rankable only when source reconciliation passes, minimum support is met, all inputs are finite, predictor population variance is finite and positive, the two-column design is full rank, coefficient is finite and nonzero, HC3 standard error is finite and positive, and raw p-value is finite.

Every candidate remains visible under the first applicable status in this precedence:

1. `OUTCOME_OR_PREDICTOR_UNAVAILABLE`;
2. `INSUFFICIENT_CONFIRMATION_SUPPORT`;
3. `ZERO_OR_NONFINITE_VARIANCE`;
4. `RANK_DEFICIENT_DESIGN`;
5. `ESTIMATOR_FAILURE`;
6. `DIRECTION_NOT_REPLICATED`;
7. `MULTIPLICITY_NOT_MET`;
8. `EFFECT_COMPATIBILITY_NOT_MET`;
9. `CONFIRMED_ASSOCIATION`.

Global source or contract reconciliation failures abort the run before candidate statuses are produced.

## Canonical outputs

A future implementation must emit exactly ten canonical files under one governed Campaign #49 artifact directory:

1. `confirmation_source_manifest.json`;
2. `confirmation_anchor_inventory.csv`;
3. `confirmation_anchor_inventory.json`;
4. `confirmation_candidate_inventory.csv`;
5. `confirmation_candidate_inventory.json`;
6. `confirmation_results.csv`;
7. `confirmation_results.json`;
8. `confirmation_group_decisions.json`;
9. `confirmation_report.md`;
10. `confirmation_manifest.json`.

All outputs must be UTF-8, LF-only, deterministically ordered, strict JSON where applicable, and free of wall-clock timestamps, machine-specific absolute paths, random identifiers, unordered mappings, and nonfinite JSON values.

## Preflight, replay, and immutability

Before any confirmation outcome is generated, preflight must verify the final frozen source identity and provenance, schema, timestamps, missing-hour inventory, positive finite closes, exact method inventories, anticipated anchor counts, and sample maturity. It must report `confirmation_outcomes_generated:false`.

Governed execution must require:

1. source hash before generation;
2. first canonical generation;
3. canonical file hashes;
4. second generation from the same source;
5. byte identity across all ten outputs;
6. post-generation preflight;
7. unchanged source bytes.

Any mismatch fails closed and prohibits publication.

## Interpretation boundary

Campaign #49 can confirm only statistical association. It cannot establish directional forecasting, deployable alpha, economic value, transaction-cost robustness, portfolio improvement, sizing, timing, Core v1 superiority, or production readiness.

Only a successful Campaign #49 result may be proposed for a later separately frozen economic-value campaign.

## Authorization boundary

This methodological lock authorizes only:

- source publication reconciliation;
- deterministic cumulative source-acquisition and historical-revision checks;
- source-only manifests;
- governance documentation;
- a later final-source annex after maturity.

It does not authorize confirmation predictor/outcome calculation, anchor construction, estimator implementation, result generation, sensitivity outcomes, economic testing, Core v1 comparison, runtime work, or strategy work.
