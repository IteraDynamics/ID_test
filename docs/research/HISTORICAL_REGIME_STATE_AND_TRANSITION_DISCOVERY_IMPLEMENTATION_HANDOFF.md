# Campaign #45 — Historical Regime State and Transition Discovery Implementation Handoff

## Status

Pre-result implementation handoff completed on `agent/campaign-45-historical-regime-transitions`.

**Decision: NO-GO for predictive implementation against the currently governed source set.**

The handoff identified a deterministic support-feasibility failure before predictive-return generation or inspection. The existing governed event-family source contains 14 independent families, while the frozen Campaign #45 specification requires at least 20 independent event families or chronologically purged observations overall for a rankable candidate. Because the governed historical collapse episodes reconcile into those event families, overlapping episode rows may not be counted as additional independent observations.

No predictive outcomes, candidate coefficients, p-values, rankings, or result artifacts were generated or inspected.

## Governing documents

- `docs/ITERA_CAMPAIGN_BOARD.md`
- `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY.md`
- specification freeze commit: `7d9cf4bb1abb556e99ffce21127cf98379dc968e`

## Resolved governed source identities

### Historical configuration

- path: `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json`
- SHA-256: `0c1ebc70007570cb7172f2a46283ab25128e1911ac34f447cc5f306c211d3a17`
- required evidence: one JSON object

### Historical episodes

- path: `artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv`
- SHA-256: `6eaadd0fd6d2231d517e5062f15bf5ea92f6bd40e3a1b1aded415e891596c143`
- required evidence: 122 rows
- governed anchor: exact `window_end`

### Episode signatures

- path: `artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv`
- SHA-256: `ccb0b748b82f7a6449b9caf945b904bfaa4871cdf2a35413c9157c41890e2327`
- required evidence: 122 rows

### Event families

- path: `artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json`
- SHA-256: `be4fc3e45f8728313a714cd5f4ea932e6822dcea138f145126f9b0392756e584`
- required evidence: 14 families
- governed family anchor: exact family `window_end`, equal to the maximum member `window_end`
- one family may contribute at most one independent observation per candidate, anchor definition, and horizon

### Event-family membership

- path: `artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv`
- SHA-256: `6bba0128dac682194da20126e1c36c81a38e809c8f8867e1a5946747e692f744`
- required evidence: 122 unique episode memberships

### BTC hourly price source

- provisioning class: externally provisioned local research input
- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: 4,792,028
- row count: 70,069
- exact ordered schema: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- first timestamp: `2018-01-01 00:00:00`
- last timestamp: `2025-12-31 00:00:00`
- timestamp convention: timezone-naive exact hourly labels
- exact timestamp matching only; no interpolation, fill, resampling, nearest-row, or as-of matching

## Timestamp and leakage contract

Eligible predictors must be available using information bounded by the exact anchor timestamp.

Eligible anchor-local components remain limited to:

- collapse severity;
- feature displacement;
- volatility-state subtype;
- intrinsic combinations composed only from eligible anchor-local components;
- prior non-identical intrinsic state when unambiguous;
- ordered prior-to-current intrinsic transition when unambiguous;
- state age and transition spacing only when exact continuity can be established.

The following remain prohibited predictors:

- recovery outcome;
- recovery duration or `recovery_rows`;
- recovered-without-retraining status;
- similarity to a later or latest window;
- any field computed using future prices or activation behavior;
- learned transition classes;
- post-result combinations.

## Representative-family anchor rule

For the currently governed episode and family sources, the only authorized representative family anchor is the existing governed family `window_end`, equal to the maximum member `window_end`.

No earliest-member, median-member, dominant-state, weighted, or outcome-dependent family anchor is authorized.

A categorical family value is available only when the required member-level information reconciles under a deterministic pre-result rule. Mixed or ambiguous families remain visible and unavailable; no dominant label may be inferred.

## Frozen controls and outcomes

If a future board transition supplies sufficient independent support, the implementation must retain the existing frozen controls:

- trailing 24-hour log return;
- trailing 72-hour log return;
- trailing 168-hour log return;
- trailing 24-hour realized volatility from hourly log returns;
- trailing 168-hour realized volatility from hourly log returns;
- distance from trailing 168-hour close mean divided by trailing 168-hour close standard deviation when finite and positive.

Frozen primary outcome:

- forward BTC log return from exact anchor close to exact horizon close.

Frozen horizons:

- 24 hours;
- 72 hours;
- 168 hours.

Maximum adverse excursion remains unauthorized until an exact formula is separately frozen.

## Planned estimator and multiplicity contract

The estimator is intentionally **not activated** because the source set fails the minimum independent-support gate before modeling.

For a future sufficient-support rerun, the implementation handoff must be amended or superseded before predictive inspection to freeze:

- exact control scaling and missing-data treatment;
- exact categorical encoding and reference levels;
- exact incremental-association estimator;
- exact standard-error or resampling method appropriate to the independent observation unit;
- exact confirmatory significance standard;
- exact multiplicity family and correction method;
- exact fold boundaries and purge behavior.

No estimator may be selected now merely to accommodate 14 observations, and no multiplicity method may be chosen after seeing outcomes.

## Deterministic support-feasibility result

Frozen minimum support gate:

- at least 20 independent event families or chronologically purged observations overall.

Governed source evidence:

- historical episodes: 122;
- unique event-family memberships: 122;
- independent event families: 14.

Result:

- maximum independent support available from the governed collapse-episode source set: 14;
- required minimum: 20;
- deficit: 6;
- implementation status: `INSUFFICIENT_INDEPENDENT_SUPPORT_PRECHECK`;
- predictive generation: prohibited;
- rankable candidates possible from the current source set: 0.

The chronologically purged fallback does not increase support for these observations because governed event-family identity applies. Overlapping episodes inside a family cannot be reclassified as separate purged observations.

## Fail-closed preflight contract

Any later implementation must stop before outcome construction unless all of the following pass:

1. every governed source exists at the exact path;
2. every source hash and declared count matches;
3. all 122 episode IDs reconcile one-to-one with the 122 event-family membership rows;
4. exactly 14 governed family identities reconcile to the family artifact for the current source version;
5. every predictor field is proven anchor-local or excluded;
6. exact timestamp semantics are established;
7. no duplicate anchors exist within the independent observation unit;
8. exact BTC anchor and required trailing-control timestamps are present;
9. exact horizon timestamps are present without interpolation;
10. fold and purge rules are frozen before outcome inspection;
11. independent support is at least 20 overall and at least 5 in every required evaluation fold;
12. the estimator and multiplicity contract have been frozen in a superseding pre-result handoff;
13. governed sources remain byte-identical before and after generation.

Failure of any item prohibits canonical predictive-result publication.

## Authorized next research choices

Campaign #45 may proceed only through a new explicit board transition that chooses one of these governance-safe paths:

1. **Extend the governed historical regime source** to a longer or broader anchor-local history that yields at least 20 genuinely independent families or purged observations, while preserving the frozen predictor and outcome concepts.
2. **Redefine the research population** around an already governed full historical state sequence rather than the collapse-only episode population, but only if exact anchor-local state labels, continuity, and timestamp semantics already exist and are frozen before outcomes.
3. **Close Campaign #45 as infeasible under current evidence** and advance to the next Campaign #44 priority.

The support threshold must not be lowered merely to make the current data pass.

## Authorization boundary

This handoff authorizes no implementation code, predictive-return generation, result inspection, canonical artifact generation, artifact publication, model training, runtime integration, threshold change, signal change, strategy change, order, execution, portfolio construction, NAV change, exposure change, dashboard change, or production behavior change.
