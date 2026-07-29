# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #45 — Historical Regime State and Transition Discovery

**Classification:** Research-only predictive discovery over the frozen canonical Campaign #46 source ledger

**Status:** PREDICTIVE IMPLEMENTATION GO — superseding specification and implementation handoff are frozen before predictive-outcome generation; deterministic observation-only implementation, focused tests, governed preflight, canonical generation, two-run replay, result inspection, full-suite validation, scope review, and publication are authorized within the frozen file surfaces and contracts

**Working branch:** `agent/campaign-45-historical-regime-transitions`

**Repository:** `IteraDynamics/ID_test`

**Governing specification:** `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY.md`

**Superseding specification freeze commit:** `8a4037b2c0ceed4eb9ff68efbf6fd082af0703a2`

**Implementation handoff:** `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY_IMPLEMENTATION_HANDOFF.md`

**Superseding handoff commit:** `a2038befea6a598bb4e2eae31f1f3fcfe1181757`

## Immediate objective

Implement the frozen Campaign #45 predictive research pipeline against the canonical Campaign #46 transition source, validate it fail-closed, reproduce canonical outputs byte-for-byte, and inspect whether any ordered BTC regime transition has multiplicity-adjusted, directionally stable incremental forward-return association.

Source feasibility is established. Predictive value is not yet known.

## Current authorization

**Decision:** GO for Campaign #45 predictive implementation under the frozen specification and handoff.

Authorized now:

- add one observation-only Campaign #45 module under `research/ml/validation/`;
- add one Campaign #45 runner under `scripts/`;
- add focused Campaign #45 tests under `tests/`;
- use only the canonical Campaign #46 transition source and governed BTC hourly source;
- construct exact 24-hour, 72-hour, and 168-hour forward log returns;
- construct the six frozen anchor-local BTC controls;
- implement development-only control scaling;
- implement OLS with HC3 covariance;
- implement the frozen support and directional-consistency gates;
- implement Benjamini-Hochberg FDR at `q = 0.05` over the frozen confirmatory family;
- generate the frozen canonical outputs;
- run governed preflight, focused tests, two-run replay, full-suite validation, scope review, and result inspection;
- publish canonical Campaign #45 artifacts after all acceptance gates pass.

Not authorized:

- changes to `BaselineRegimeEngine`, regime labels, thresholds, or classifier defaults;
- model training, replacement, or recalibration;
- new predictors, outcomes, controls, horizons, interactions, transformations, estimators, or multiplicity methods outside the frozen documents;
- signals, strategy changes, orders, execution, portfolio construction, NAV, exposure, or dashboard changes;
- production or paper-runtime integration;
- interpolation, filling, resampling, nearest-row matching, as-of matching, or source substitution;
- interpreting statistical association as deployable alpha or strategy usefulness.

## Frozen research contract

### Source

Canonical Campaign #46 directory:

`artifacts/full_historical_regime_state_sequence/`

Publication commit: `34a6999`.

Required evidence:

- total transitions: `2,789`;
- eligible non-`UNKNOWN` transitions: `2,788`;
- frozen 168-hour purged transitions: `242`;
- chronological evidence partitions: `81`, `81`, `80`;
- feasibility status: `CAMPAIGN_45_SOURCE_FEASIBLE`;
- Campaign #46 predictive outcomes generated: `false`.

Underlying BTC source:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- byte count: `4,792,028`;
- rows: `70,069`;
- timestamps: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`;
- exact timestamp matching only.

### Confirmatory candidates

Exact ordered non-`UNKNOWN`, non-self transition categories crossed with horizons:

- 24 hours;
- 72 hours;
- 168 hours.

### Controls

- trailing 24-hour log return;
- trailing 72-hour log return;
- trailing 168-hour log return;
- trailing 24-hour realized volatility;
- trailing 168-hour realized volatility;
- normalized distance from trailing 168-hour close mean.

### Estimator

Ordinary least squares with intercept, binary candidate indicator, six development-standardized controls, and HC3 heteroskedasticity-consistent covariance.

### Multiplicity

Benjamini-Hochberg FDR at `q = 0.05` over all rankable ordered-transition-by-horizon pooled tests.

### Chronological evaluation

- partition 1: initial development;
- partition 2: evaluation using partition 1 only;
- partition 3: evaluation using partitions 1 and 2 only.

A candidate must have finite nonzero coefficients of the same sign in both evaluation partitions and a pooled coefficient of that same sign.

### Minimum support

- at least 20 independent observations overall;
- at least 5 candidate observations in each evidence partition;
- at least 5 candidate-present and 5 candidate-absent observations in each required estimator sample.

## Governing constraints

All work must remain deterministic, replay-safe, research-only, observation-only, anchor-local, leakage-safe, fail-closed, and independent of production runtime state mutation.

Any disagreement between the source contract, canonical artifacts, specification, handoff, implementation, runner, tests, or generated manifests fails closed.

No threshold, signal, order, execution, portfolio, NAV, exposure, model, strategy, or dashboard change is authorized.

## Authorized file surfaces

Campaign #45 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY.md`;
- `docs/research/HISTORICAL_REGIME_STATE_AND_TRANSITION_DISCOVERY_IMPLEMENTATION_HANDOFF.md`;
- one new observation-only module under `research/ml/validation/`;
- one new runner under `scripts/`;
- focused Campaign #45 tests under `tests/`;
- `artifacts/historical_regime_transitions/**`.

Any additional surface requires an explicit board transition.

## Acceptance gates

1. Superseding specification predates predictive-result generation. **Passed: `8a4037b`.**
2. Superseding handoff predates predictive-result generation. **Passed: `a2038be`.**
3. Governed identities, hashes, schemas, counts, ordering, timestamps, purge membership, and partitions pass preflight. **Pending.**
4. Focused Campaign #45 tests pass. **Pending.**
5. Exact anchor, candidate, and fold inventories serialize deterministically before ranking. **Pending.**
6. Controls, development-only scaling, outcomes, OLS, HC3, support gates, BH correction, and directional rules reconcile exactly. **Pending.**
7. Null, missing, failed, and insufficient-support candidates remain visible. **Pending.**
8. Two governed runs produce byte-identical canonical outputs. **Pending.**
9. Canonical text is LF-only and JSON is strict. **Pending.**
10. Governed sources remain byte-identical before and after generation. **Pending.**
11. Full repository suite passes with no new failures. **Pending.**
12. Scope review finds no production, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes. **Must remain true.**
13. Any statistical result remains research-only and does not authorize strategy use. **Must remain true.**

## Immediate sequence

1. Close Campaign #46 and publish its canonical source. **Completed.**
2. Reactivate Campaign #45 for governance. **Completed.**
3. Supersede and freeze the Campaign #45 specification. **Completed: `8a4037b`.**
4. Supersede and freeze the implementation handoff. **Completed: `a2038be`.**
5. Record the separate predictive implementation GO. **Completed by this board transition.**
6. Implement the observation-only module, runner, and focused tests. **Authorized next.**
7. Run governed preflight before outcome construction. **Pending.**
8. Generate canonical outputs twice and verify byte identity. **Pending.**
9. Run the full repository suite and scope review. **Pending.**
10. Inspect and publish the governed result. **Pending.**

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

## Research boundary

Campaign #45 distinguishes:

1. source feasibility — answered yes;
2. predictive evidence — authorized for governed testing, not yet known;
3. strategy usefulness — not authorized and cannot be inferred directly.

A statistically interesting transition does not authorize runtime use, threshold changes, signal generation, order generation, portfolio construction, NAV changes, or exposure changes.

## Campaign #44 priority context

Campaign #44 ranked:

1. S-002 — Historical regime state and transition structure: 29;
2. S-003 — Historical event persistence, clustering, duration, and spacing: 27;
3. S-008 — Simple BTC price-state baselines: 26;
4. S-001 — Registered Core v1 collapse structure candidate A-001: 26.

Campaign #46 supplied the source infrastructure required to test S-002 responsibly. Campaign #45 is the governed predictive discovery campaign for that priority.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #45 or Campaign #46 unless separately authorized.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #45 authorization.