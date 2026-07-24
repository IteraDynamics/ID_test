# Core v1 Historical Alpha Discovery

## Status

Frozen governing research specification for Campaign #43.

This specification is committed before predictive result inspection, candidate optimization, implementation output generation, or canonical ranking.

## Purpose

Campaign #43 is the first Itera campaign explicitly intended to discover candidate historical predictive relationships.

Its purpose is to identify which existing governed Core v1 descriptors exhibit repeatable out-of-sample association with deterministic forward BTC outcomes after correcting overlapping episode duplication through Campaign #41 event families.

The campaign produces candidate evidence, including null and contradictory evidence. It does not produce a trading strategy or authorize production use.

## Safety boundary

The work is BTC-only, deterministic, replay-safe, research-only, observation-only, and fail-closed.

It does not authorize production runtime integration, live signals, model training or replacement, threshold changes, signal or intent changes, orders, execution, portfolio construction, NAV changes, exposure mutation, dashboard integration, cross-asset work, transaction-cost claims, deployable-alpha claims, or strategy recommendations.

## Frozen governed sources

The implementation may consume only the following repository-relative artifacts at the exact SHA-256 identities below.

| Source | Path | SHA-256 | Required evidence |
|---|---|---|---|
| Historical configuration | `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json` | `0c1ebc70007570cb7172f2a46283ab25128e1911ac34f447cc5f306c211d3a17` | one JSON object |
| Historical episodes | `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv` | `6eaadd0fd6d2231d517e5062f15bf5ea92f6bd40e3a1b1aded415e891596c143` | 122 rows |
| Episode signatures | `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv` | `ccb0b748b82f7a6449b9caf945b904bfaa4871cdf2a35413c9157c41890e2327` | 122 rows |
| Event families | `artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json` | `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584` | 14 families |
| Event-family membership | `artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv` | `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744` | 122 unique episode memberships |
| Campaign #42 robustness result | `artifacts/core_v1_event_robustness/btc_extended_up_event_robustness.json` | `578d8e7c0176489ff5b67761b48ece8bac3285ba06b70ae6ee5d8fe93abb0dc7` | reconciliation only |
| Governed hourly BTC series | `artifacts/jump_risk_portfolio_v0/20260716T125121Z_jump-risk-portfolio-integration-v0/predictions/btc_extended_up.csv` | `36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7` | 52,453 rows; first timestamp `2020-01-01 01:00:00`; last timestamp `2025-12-26 00:00:00`; timezone-naive; strictly increasing; no duplicate timestamps |

Every source must exist, match its hash, match its declared row/count evidence, remain unchanged before and after generation, and reconcile to the Campaign #41 identities. Any disagreement fails closed.

The governed hourly BTC series must contain an exact column named `close`. `close` must be finite, strictly positive, and aligned one-to-one with the governed timestamp index. No alternate price field may be inferred. If the exact governed artifact does not contain `close`, implementation must stop and the board must transition to an explicitly governed price source before results are generated.

## Units of observation

### Episode resolution

Each of the 122 governed episodes contributes one rolling-window observation. Episode evidence is descriptive of overlapping observations and must never be represented as independent-event support.

The episode anchor is the exact governed `window_end` timestamp. All candidate fields used at episode resolution must be deterministically available from information bounded by that timestamp.

### Event-family resolution

Each of the 14 Campaign #41 event families contributes at most one independent-event-correction observation per candidate value and horizon.

The family anchor is the exact governed family `window_end`, equal to the maximum member `window_end`. This rule is fixed without reference to outcomes.

A family contributes to a categorical candidate value only when every member has the same value. Mixed families are recorded as unavailable for that candidate and are not coerced, pluralized, weighted, or assigned a dominant value.

## Frozen candidate inventory

Campaign #43 initial candidates are categorical values from these five pre-existing, deterministic descriptors:

1. `collapse_severity`;
2. `feature_displacement`;
3. `volatility_state`;
4. `intrinsic_subtype`, defined exactly as `collapse_severity + "__" + feature_displacement + "__" + volatility_state`;
5. `activation_ratio_band`, derived only from the already-governed thresholds that define `collapse_severity`, with the exact values `SEVERE_COLLAPSE`, `MAJOR_COLLAPSE`, and `MODERATE_COLLAPSE`; this is an alias audit of `collapse_severity`, not an additional independent candidate and must be emitted as `alias_of=collapse_severity` rather than double-ranked.

The rankable inventory is therefore the first four descriptors only. Candidate rows are exact `(descriptor, value, horizon_hours)` combinations.

### Explicit exclusions

The following are ineligible in Campaign #43:

- `recovery_outcome`, `recovered_without_retraining`, and `recovery_rows`, because they use information observed after the episode anchor and would create look-ahead if treated as predictors;
- `feature_cosine_similarity_to_latest` and `similarity_band`, because their reference to the latest window is not an anchor-local historical quantity;
- episode IDs, family IDs, ordinals, timestamps, and source row positions as predictors;
- arbitrary interactions or transformed thresholds not listed above;
- any candidate invented or selected after outcome inspection.

Excluded fields may appear only in reconciliation diagnostics where they cannot influence ranking.

## Frozen forward outcomes

For anchor timestamp `t`, horizon `h`, anchor close `C_t`, and exact future hourly closes through `t+h`:

1. `forward_return = C_(t+h) / C_t - 1`;
2. `positive_return = forward_return > 0`;
3. `maximum_favorable_excursion = max(C_(t+1), ..., C_(t+h)) / C_t - 1`;
4. `maximum_adverse_excursion = min(C_(t+1), ..., C_(t+h)) / C_t - 1`;
5. `realized_volatility = population_standard_deviation(log(C_i / C_(i-1)))` for the `h` exact one-hour returns after `t`.

Price matching is exact timestamp matching only. No as-of match, interpolation, forward fill, backward fill, resampling, gap filling, or inferred cadence is allowed.

An observation is unavailable for a horizon unless the anchor and every exact hourly timestamp through `t+h` exist. Unavailable observations remain visible in diagnostics and do not enter metrics.

No outcome incorporates costs, slippage, leverage, sizing, execution, stops, targets, or portfolio behavior.

## Frozen horizons

The exact horizon set is:

- 2 hours;
- 6 hours;
- 24 hours;
- 72 hours;
- 168 hours.

No horizon may be added, removed, substituted, or selectively reported after result inspection without a new board transition and a separately designated rerun.

## Frozen chronological evaluation

Random splits are prohibited.

Event families are ordered by `(window_end, window_start, family_id)` using stable ascending order. The 14-family history is divided into the following fixed expanding-window folds by ordered zero-based family position:

| Fold | Training family positions | Test family positions |
|---|---|---|
| 0 | `0..4` | `5..7` |
| 1 | `0..7` | `8..10` |
| 2 | `0..10` | `11..13` |

Fold boundaries are defined only by ordered family identity and not by outcomes.

Episode-resolution folds use the same three temporal test intervals. An episode belongs to a test fold when its `window_end` is greater than the latest training-family anchor and less than or equal to the latest test-family anchor. Episodes at or before the training boundary are training observations. Episodes after the test boundary are unavailable to that fold. No episode may appear in more than one test fold.

Campaign #43 does not fit a predictive model. Training partitions are retained to enforce chronology and to calculate a training-direction baseline. Test partitions provide the out-of-sample evidence.

For each candidate value and horizon in each fold:

- training direction is `sign(median training forward_return)`;
- test direction is `sign(median test forward_return)`;
- zero is a distinct direction;
- no direction is emitted when support is insufficient.

## Frozen support rules

A candidate-value-horizon row is `eligible` only when all of the following hold:

1. total episode support is at least 5;
2. total homogeneous event-family support is at least 3;
3. at least 2 of the 3 folds contain at least 1 homogeneous test family for the value;
4. every counted observation has complete exact hourly coverage for the horizon;
5. all emitted metrics are finite.

A fold direction comparison is supported only when training has at least 2 homogeneous families and test has at least 1 homogeneous family for that value.

Support thresholds are evidence gates, not trading thresholds, and do not affect runtime behavior.

## Frozen evidence metrics

For each rankable `(descriptor, value, horizon_hours)` row, report:

- episode support and unavailable episode count;
- homogeneous event-family support and mixed/unavailable family count;
- supported fold count;
- episode mean and median forward return;
- family mean and median forward return;
- episode and family positive-return rate;
- family mean maximum favorable excursion;
- family mean maximum adverse excursion;
- family mean realized volatility;
- count of supported folds where training and test direction agree;
- count of supported folds where the test direction agrees with the aggregate family direction;
- episode-versus-family median-return sign agreement;
- absolute episode-versus-family median-return divergence;
- evidence state.

No p-value, confidence label, Sharpe ratio, alpha estimate, annualization, optimized score, or deployable-strategy score is authorized.

## Frozen evidence states

Evidence state is assigned in this order:

1. `SOURCE_INVALID` for any governed-source failure; canonical result publication is prohibited;
2. `OUTCOME_UNAVAILABLE` when complete exact horizon coverage is absent for all observations;
3. `INSUFFICIENT_SUPPORT` when any eligibility support gate fails;
4. `CONTRADICTORY_RESOLUTION` when non-zero episode and family median-return signs disagree;
5. `UNSTABLE_OOS` when fewer than all supported folds agree with aggregate family direction or fewer than all supported folds have training/test direction agreement;
6. `NULL_ASSOCIATION` when eligible and the aggregate family median forward return is exactly zero;
7. `SUPPORTED_ASSOCIATION` only when eligible, resolution signs agree, and every supported fold is directionally stable under both comparisons.

These states describe historical evidence only.

## Frozen deterministic ranking

All rows, including null and failed rows, remain in canonical outputs.

Rows are sorted lexicographically by the following tuple:

1. evidence-state order: `SUPPORTED_ASSOCIATION`, `NULL_ASSOCIATION`, `UNSTABLE_OOS`, `CONTRADICTORY_RESOLUTION`, `INSUFFICIENT_SUPPORT`, `OUTCOME_UNAVAILABLE`;
2. descending supported-fold count;
3. descending training/test direction-agreement count;
4. descending aggregate-direction-agreement count;
5. descending homogeneous family support;
6. descending absolute family median forward return;
7. ascending horizon hours;
8. ascending descriptor;
9. ascending candidate value.

No weights are fitted. No ranking term may be changed after result inspection.

The report must state that high rank is a prioritization aid for later falsification, not evidence of deployable alpha.

## Canonical outputs

Under `artifacts/core_v1_historical_alpha_discovery/`:

- `btc_core_v1_alpha_candidates.json`;
- `btc_core_v1_alpha_candidates.csv`;
- `btc_core_v1_alpha_discovery_folds.csv`;
- `btc_core_v1_alpha_discovery_report.md`;
- `btc_core_v1_alpha_discovery_manifest.json`.

The fold diagnostic is required because fold-level support and direction must reconcile to candidate rankings.

## Serialization and replay requirements

- deterministic stable sorting;
- strict JSON with sorted keys and `allow_nan=false`;
- finite numeric output only;
- LF-only text;
- no generated timestamps in canonical payloads;
- deterministic payload digest;
- newly created or explicitly empty output directory only;
- staging-directory publication and atomic replacement;
- no governed-source overwrite;
- source hashes verified before and after generation;
- two governed runs must be byte-identical.

## Required tests

Focused tests must cover at least:

- all source paths, hashes, counts, and timestamps;
- exact `close`-column requirement;
- candidate inventory and explicit leakage exclusions;
- chronological family ordering and fixed folds;
- episode-to-fold assignment;
- no-look-ahead outcome construction;
- exact timestamp coverage and gap failure;
- event-family homogeneous-only aggregation;
- mixed-family unavailability;
- support gates;
- each evidence state;
- deterministic ranking;
- strict finite serialization;
- replay byte identity;
- output-directory fail-closed behavior;
- governed-source immutability.

## Acceptance gates

1. This frozen specification is committed before implementation result inspection.
2. Exact governed paths, hashes, candidate inventory, outcomes, horizons, anchors, folds, support rules, states, ranking, and outputs remain unchanged through the governed run unless a board transition explicitly starts a new rerun designation.
3. Focused Campaign #43 tests pass.
4. Full repository suite passes with no new failures.
5. Two governed runs produce byte-identical outputs.
6. Canonical text outputs are LF-only.
7. Governed source identities and hashes remain unchanged.
8. Episode, family, mixed-family, unavailable-outcome, and fold counts reconcile.
9. Chronological folds contain no look-ahead.
10. Null, insufficient-support, contradictory, unstable, and unavailable evidence remain visible and fail closed.
11. Scope review finds no runtime, strategy, training, threshold, signal, order, portfolio, NAV, exposure, or dashboard changes.
12. The report makes no deployable-alpha or production recommendation.

## Implementation authorization

**GO, subject to source preflight.**

Implementation may begin only by validating the frozen sources and schemas. Predictive metrics and canonical artifacts may be generated only if every source, including the exact governed `close` series, passes preflight without inference or substitution.
