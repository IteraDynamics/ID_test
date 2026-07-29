# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #47 — Historical Regime Persistence, Duration, Clustering, and Spacing Discovery

**Classification:** Research-only predictive-structure governance over the frozen canonical Campaign #46 regime-state ledger

**Status:** SPECIFICATION AND IMPLEMENTATION HANDOFF FROZEN — governance design is complete before predictive outcome generation; implementation, estimator execution, result inspection, candidate ranking, artifact generation, strategy testing, and runtime integration remain unauthorized until a separate implementation GO is recorded

**Working branch:** `agent/campaign-47-regime-persistence-structure`

**Repository:** `IteraDynamics/ID_test`

**Governing specification:** `docs/research/HISTORICAL_REGIME_PERSISTENCE_DURATION_CLUSTERING_AND_SPACING_DISCOVERY.md`

**Specification freeze commit:** `bc715119d93d44b8991e02e4afb5a71d5e150c70`

**Implementation handoff:** `docs/research/HISTORICAL_REGIME_PERSISTENCE_DURATION_CLUSTERING_AND_SPACING_DISCOVERY_IMPLEMENTATION_HANDOFF.md`

**Implementation handoff freeze commit:** `fd41466aa19e32dcec40581975c87130053162c1`

## Immediate objective

Review the frozen Campaign #47 research contract and implementation handoff, verify that they preserve deterministic, replay-safe, observation-only, leakage-safe, fail-closed behavior, and decide whether to record a separate implementation GO.

Campaign #47 asks whether broadly supported temporal properties of BTC regimes contain incremental information beyond exact transition identity and recent BTC price state:

- current regime age;
- previous completed regime duration;
- time since the previous transition;
- transition density over trailing 24, 72, and 168 hours.

The frozen outcomes are directional forward return, absolute forward return, forward realized volatility, and uninterrupted current-regime survival at exact 24-, 72-, and 168-hour horizons.

## Current authorization

**Decision:** GO for Campaign #47 governance review only.

Authorized now:

- inspect and review the frozen specification and implementation handoff;
- verify source, anchor, predictor, outcome, control, estimator, support, multiplicity, serialization, and acceptance-gate definitions;
- correct only pre-result governance ambiguity through an explicitly superseding specification or handoff commit;
- record a separate implementation GO only after the frozen documents are accepted.

Not authorized:

- implementation of the Campaign #47 module, runner, or tests;
- predictive outcome generation or inspection;
- estimator execution, p-values, q-values, effect sizes, direction tests, or candidate ranking;
- changes to `BaselineRegimeEngine`, canonical Campaign #46 labels, thresholds, or classifier defaults;
- model training, replacement, or recalibration;
- Core v1 overlay or economic-value testing;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, or optimization research under Campaign #47;
- signals, strategy changes, orders, execution, portfolio construction, NAV, exposure, dashboard changes, or runtime integration;
- interpolation, filling, resampling, nearest-row matching, as-of matching, synthetic bars, or source substitution.

## Frozen Campaign #47 research contract

### Source

Canonical Campaign #46 directory:

`artifacts/full_historical_regime_state_sequence/`

Campaign #46 publication commit: `34a6999`.

Required canonical files:

- `btc_hourly_regime_state_manifest.json`;
- `btc_hourly_regime_state_sequence.csv`;
- `btc_hourly_regime_state_runs.csv`;
- `btc_hourly_regime_transitions.csv`.

Underlying BTC source:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- byte count: `4,792,028`;
- rows: `70,069`;
- timestamps: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`;
- exact timestamp matching only.

### Anchors

- one common deterministic 168-hour anchor grid;
- origin at the earliest eligible canonical non-`UNKNOWN` state row with all 168-hour trailing controls available;
- exact 168-hour timestamp increments only;
- no shifting or nearest-row replacement when a scheduled timestamp is absent;
- three contiguous near-equal chronological partitions, with remainder rows assigned to earlier partitions;
- anchor and partition inventories serialized before result ranking.

### Structural predictors

1. `log1p_current_state_age_hours`;
2. `log1p_previous_state_duration_hours`;
3. `log1p_hours_since_previous_transition`;
4. `transition_count_trailing_24h`;
5. `transition_count_trailing_72h`;
6. `transition_count_trailing_168h`.

No thresholds, bins, interactions, splines, polynomial terms, or data-dependent feature selection are authorized.

### Outcomes

At exact 24-, 72-, and 168-hour horizons:

- Family R: directional forward log return;
- Family M: absolute forward log return;
- Family V: forward realized volatility using every exact hourly return in the interval;
- Family S: uninterrupted current-regime survival indicator.

Any missing exact timestamp required by an outcome makes that outcome unavailable. No filling is permitted.

### Controls and estimator

Each candidate uses:

- trailing 24-, 72-, and 168-hour log returns;
- trailing 24- and 168-hour realized volatility;
- normalized distance from trailing 168-hour close mean;
- development-defined current-regime fixed effects.

Continuous predictors and controls are standardized using development rows only for chronological evaluations.

Estimator:

- ordinary least squares with intercept;
- one structural predictor;
- six continuous controls;
- current-regime fixed effects;
- HC3 covariance;
- two-sided normal p-value;
- 95% normal confidence interval.

Family S uses the same specification as a linear probability model and makes no calibrated-probability claim.

### Candidate family and multiplicity

- 6 predictors;
- 4 outcome families;
- 3 horizons;
- 72 frozen candidates.

Benjamini-Hochberg FDR at `q = 0.05` is applied separately within each prespecified 18-test outcome family.

### Support and directional consistency

A candidate requires at least:

- 90 complete pooled anchors;
- 25 complete anchors in each chronological partition;
- finite, nonconstant predictors and controls;
- full-rank estimator designs;
- finite nonzero coefficients;
- finite strictly positive HC3 standard errors;
- no development-absent regime level in an evaluation sample.

A supported research association requires:

- BH-adjusted family q-value `<= 0.05`; and
- finite nonzero coefficients of the same sign in partition-2 evaluation, partition-3 evaluation, and the pooled fit.

Unrankable, null, missing, failed, and insufficient-support candidates must remain visible.

A supported association does not establish deployable alpha, economic usefulness, or strategy value.

## Campaign #47 authorized file surfaces after separate implementation GO

Campaign #47 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/HISTORICAL_REGIME_PERSISTENCE_DURATION_CLUSTERING_AND_SPACING_DISCOVERY.md`;
- `docs/research/HISTORICAL_REGIME_PERSISTENCE_DURATION_CLUSTERING_AND_SPACING_DISCOVERY_IMPLEMENTATION_HANDOFF.md`;
- `research/ml/validation/historical_regime_structure_discovery.py`;
- `scripts/run_historical_regime_structure_discovery.py`;
- `tests/test_historical_regime_structure_discovery.py`;
- `artifacts/historical_regime_structure/**`.

Any additional surface requires an explicit board transition.

## Campaign #47 acceptance gates

1. The frozen specification predates predictive outcome generation. **Passed: `bc71511`.**
2. The frozen implementation handoff predates predictive outcome generation. **Passed: `fd41466`.**
3. A separate implementation GO is recorded. **Pending.**
4. Governed source identities, hashes, schemas, ordering, state/run/transition relationships, and timestamps pass preflight. **Pending.**
5. Exact anchor, predictor, candidate, outcome, and partition inventories serialize deterministically before ranking. **Pending.**
6. Focused Campaign #47 tests pass. **Pending.**
7. Controls, transformations, development-only scaling, fixed effects, outcomes, OLS, HC3, support gates, direction rules, and family-specific BH correction reconcile exactly. **Pending.**
8. Null, missing, failed, and insufficient-support candidates remain visible. **Pending.**
9. Two governed runs produce byte-identical canonical outputs. **Pending.**
10. Canonical text is LF-only and JSON is strict. **Pending.**
11. Governed source bytes remain identical before and after generation. **Pending.**
12. Full repository suite passes with no new failures. **Pending.**
13. Scope review finds no runtime, threshold, regime, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training changes. **Must remain true.**
14. Any supported candidate remains research-only and enters a separate confirmation campaign before any Core v1 overlay test. **Must remain true.**

## Immediate sequence

1. Complete and merge Campaign #45 on its governed research lineage. **Completed: PR #43, merge `42e5d7c`.**
2. Freeze the Campaign #47 specification before predictive outcome generation. **Completed: `bc71511`.**
3. Freeze the Campaign #47 implementation handoff before predictive outcome generation. **Completed: `fd41466`.**
4. Review the frozen Campaign #47 design. **Authorized next.**
5. Record a separate Campaign #47 implementation GO if the design is accepted. **Pending.**
6. Implement the observation-only module, runner, and focused tests. **Not yet authorized.**
7. Run governed preflight before outcome construction. **Pending.**
8. Generate canonical outputs twice and verify byte identity. **Pending.**
9. Inspect results, run the full suite, and perform scope review. **Pending.**
10. Publish and close Campaign #47 only if every acceptance gate passes. **Pending.**

## Campaign #45 completion record

**Campaign:** Campaign #45 — Historical Regime State and Transition Discovery

**Final status:** COMPLETE — canonical artifacts published; no supported exact ordered-transition association

**Working branch:** `agent/campaign-45-historical-regime-transitions`

**Publication commit:** `5fa4b8434ed4927e69b8cc973ba0009f99215a24`

**Pull request:** PR #43

**Governed merge commit:** `42e5d7c47d90e1941e61e0e229d4fa71da07b449`

Completed evidence:

- focused suite: `24 passed`;
- governed preflight: `PASS`;
- source transitions: `2,789`;
- eligible non-`UNKNOWN` transitions: `2,788`;
- independent 168-hour-purged anchors: `242`;
- partitions: `81`, `81`, `80`;
- candidate-horizon tests: `51`;
- rankable candidates: `9`;
- insufficient binary-side support: `42`;
- supported associations: `0`;
- two governed runs completed successfully;
- all ten canonical outputs byte-identical across replay;
- canonical staged files LF-only and reconciled to their manifest;
- governed source bytes unchanged before and after generation;
- full repository suite: `483 passed`, `75 warnings`;
- final Campaign #45 comparison: exactly `13` authorized paths;
- branch diff check: clean.

Campaign #45 conclusion:

No exact ordered BTC regime transition met the frozen multiplicity-adjusted and directional-consistency requirements for incremental 24-hour, 72-hour, or 168-hour forward-return association after controlling for the six frozen BTC price-state controls.

This negative result weakens exact ordered-transition identity as a standalone predictive feature. It does not show that regimes, duration, persistence, clustering, volatility conditioning, risk estimation, or later confirmed overlays are useless. It authorizes no runtime, threshold, signal, strategy, order, portfolio, NAV, exposure, dashboard, or model-training change.

## Campaign #46 completion record

**Campaign:** Campaign #46 — Full Historical Regime State Sequence

**Final status:** COMPLETE — canonical artifacts published; `CAMPAIGN_45_SOURCE_FEASIBLE`

**Working branch:** `agent/campaign-46-full-regime-state-source`

**Canonical publication commit:** `34a6999`

Completed evidence:

- focused suite: `10 passed`;
- governed preflight: `PASS`;
- two-run replay: all eight files byte-identical;
- state rows: `70,069`;
- total transitions: `2,789`;
- eligible transitions: `2,788`;
- independent purged transitions: `242`;
- partition counts: `81`, `81`, `80`;
- predictive outcomes generated: `false`;
- full repository suite: `459 passed`, `75 warnings`.

Campaign #46 made no predictive, economic, directional, or alpha claim.

## Research-priority context

Campaign #44 ranked:

1. S-002 — Historical regime state and transition structure: 29;
2. S-003 — Historical event persistence, clustering, duration, and spacing: 27;
3. S-008 — Simple BTC price-state baselines: 26;
4. S-001 — Registered Core v1 collapse structure candidate A-001: 26.

Campaign #45 completed the governed predictive test of sparse exact ordered-transition identity for S-002. Campaign #47 advances S-003 using broadly supported continuous temporal structure rather than exact transition categories.

## Research progression boundary

Campaign #47 is a discovery campaign. Any supported association must enter a separately frozen confirmation campaign. Only candidates that survive confirmation may enter a later separately authorized incremental-value comparison against untouched Core v1 using Sharpe, CAGR, drawdown, turnover, exposure, and related economic metrics.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #47 unless separately authorized.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #47 authorization.