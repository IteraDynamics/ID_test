# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #45 — Historical Regime State and Transition Discovery

**Classification:** Research-only predictive discovery over the frozen canonical Campaign #46 source ledger

**Status:** REACTIVATION AUTHORIZED FOR GOVERNANCE ONLY — Campaign #46 is complete and its canonical source-support result is `CAMPAIGN_45_SOURCE_FEASIBLE`; Campaign #45 specification review, support-gate reconciliation, and implementation handoff may proceed, but predictive implementation, forward-return generation, estimator execution, result inspection, and candidate ranking remain unauthorized until a separate frozen implementation GO is recorded

**Working branch:** to be created after Campaign #45 specification and implementation handoff are reconciled and frozen

**Repository:** `IteraDynamics/ID_test`

## Immediate objective

Reconcile Campaign #45's frozen research question and support gates against the canonical Campaign #46 historical regime-state source, then freeze a deterministic, leakage-safe, observation-only implementation handoff before any predictive outcomes are generated or inspected.

Campaign #45 is intended to determine whether any governed BTC regime state or ordered regime transition contains reproducible forward-return information worth further research. Source feasibility is established; predictive value is not.

## Current authorization

**Decision:** GO for Campaign #45 governance and design reconciliation only.

Authorized now:

- inspect the existing Campaign #45 specification and prior handoff;
- reconcile its source contract to the canonical Campaign #46 artifacts;
- preserve the frozen 168-hour independence purge and three chronological folds unless an explicit pre-result governance amendment is justified and recorded;
- define exact forward-return horizons, estimators, nulls, multiple-testing controls, minimum support, fold-consistency rules, failure states, and canonical outputs before result inspection;
- freeze a revised or superseding Campaign #45 specification and implementation handoff;
- update this board with a separate predictive implementation GO only after those documents are frozen.

Not authorized:

- generation or inspection of forward returns;
- predictive coefficients, p-values, effect sizes, direction tests, candidate ranking, or alpha claims;
- changes to `BaselineRegimeEngine`, regime labels, thresholds, or classifier defaults;
- model training, replacement, or recalibration;
- signals, strategy changes, orders, execution, portfolio construction, NAV, exposure, or dashboard changes;
- production or paper-runtime integration;
- any use of ungoverned source substitutions, interpolation, filling, resampling, nearest-row matching, or as-of matching.

## Governing Campaign #46 source

Campaign #45 must use the canonical Campaign #46 publication at:

`artifacts/full_historical_regime_state_sequence/`

Published files:

- `btc_hourly_regime_state_sequence.csv`
- `btc_hourly_regime_state_sequence.json`
- `btc_hourly_regime_state_runs.csv`
- `btc_hourly_regime_transitions.csv`
- `btc_hourly_regime_transitions.json`
- `btc_hourly_regime_support_feasibility.json`
- `btc_hourly_regime_state_report.md`
- `btc_hourly_regime_state_manifest.json`

Publication commit:

`34a6999`

The canonical source remains derived from:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- rows: `70,069`
- timestamps: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- discontinuities: `14`
- missing hourly timestamps: `36`
- largest elapsed interval: `16` hours
- largest missing block: `15` timestamps

Classifier input remains immutable:

- file: `research/regimes/baseline_engine.py`
- class: `BaselineRegimeEngine`
- method: `classify_dataframe()`
- constructor defaults only.

## Campaign #46 completion record

**Campaign:** Campaign #46 — Full Historical Regime State Sequence

**Classification:** Research infrastructure; deterministic source-foundation and support-feasibility construction

**Final status:** COMPLETE — canonical artifacts published; `CAMPAIGN_45_SOURCE_FEASIBLE`

**Working branch:** `agent/campaign-46-full-regime-state-source`

**Specification:** `docs/research/FULL_HISTORICAL_REGIME_STATE_SEQUENCE.md`

**Specification freeze commit:** `e3e2fe0fcdf7a00cea53adcdb4bc4c62445cb785`

**Implementation handoff:** `docs/research/FULL_HISTORICAL_REGIME_STATE_SEQUENCE_IMPLEMENTATION_HANDOFF.md`

**Handoff commit:** `d5d240e4cf1400c1dec1071bf9644d6aedb3611d`

**Source-gap correction commits:**

- runner correction: `c606e2f19dab954a06bcee288971dfa181881e52`
- specification correction: `9be6f532920ff66693b652a5cec38ff26ce4425b`
- handoff correction: `98179f002c84ea334256e735e68d409a09b96dba`

**Canonical publication commit:** `34a6999`

### Completed evidence

- focused suite: `10 passed`;
- governed preflight: `PASS`;
- canonical generator status: `PASS`;
- two-run replay: all eight canonical files byte-identical;
- state rows: `70,069`;
- total transition count: `2,789`;
- eligible non-`UNKNOWN` transition count: `2,788`;
- deterministic 168-hour purged transition count: `242`;
- chronological fold counts: `81`, `81`, `80`;
- overall minimum met: `true`;
- each-fold minimum met: `true`;
- predictive outcomes generated: `false`;
- support status: `CAMPAIGN_45_SOURCE_FEASIBLE`;
- full repository suite: `459 passed`, `75 warnings`;
- tracked scope review: no tracked modifications outside the eight authorized canonical artifact files;
- canonical artifacts published under the authorized artifact directory only.

The full-suite warnings were deprecation warnings and did not produce failures.

### Campaign #46 conclusion

Campaign #46 established that the governed historical regime ledger contains enough chronologically independent non-`UNKNOWN` transitions to satisfy Campaign #45's frozen source-support gates. It made no predictive, economic, directional, or alpha claim.

## Campaign #45 research boundary

Campaign #45 must distinguish three separate questions:

1. **Source feasibility:** already answered yes by Campaign #46.
2. **Predictive evidence:** not yet tested.
3. **Strategy usefulness:** not authorized and cannot be inferred directly from predictive evidence.

Any future Campaign #45 result must remain research-only and observation-only. A statistically interesting transition does not authorize runtime use, threshold changes, signal generation, order generation, portfolio construction, NAV changes, or exposure changes.

## Governing constraints

All work must remain deterministic, replay-safe, research-only, observation-only, anchor-local, leakage-safe, fail-closed, and independent of production runtime state mutation.

No threshold, signal, order, execution, portfolio, NAV, exposure, model, strategy, or dashboard change is authorized.

Any disagreement between the frozen source contract, classifier identity, canonical artifacts, specification, handoff, runner, or tests must fail closed before outcomes are generated.

## Immediate sequence

1. Close Campaign #46 on the authoritative board. **Completed.**
2. Record Campaign #46 publication commit and canonical feasibility evidence. **Completed.**
3. Reactivate Campaign #45 for governance-only reconciliation. **Completed.**
4. Locate and review the existing Campaign #45 specification and implementation handoff. **Authorized next.**
5. Reconcile Campaign #45's source contract to the canonical Campaign #46 artifacts. **Pending.**
6. Freeze exact horizons, estimators, nulls, multiple-testing controls, support rules, folds, failure states, and output contracts before result inspection. **Pending.**
7. Freeze the Campaign #45 implementation handoff. **Pending.**
8. Record a separate predictive implementation GO. **Pending.**
9. Only then implement, test, replay, and inspect Campaign #45 predictive outputs. **Unauthorized until step 8.**

## Campaign #44 priority context

Campaign #44 ranked:

1. S-002 — Historical regime state and transition structure: 29
2. S-003 — Historical event persistence, clustering, duration, and spacing: 27
3. S-008 — Simple BTC price-state baselines: 26
4. S-001 — Registered Core v1 collapse structure candidate A-001: 26

Campaign #46 supplied the canonical source infrastructure required to test S-002 responsibly. Campaign #45 is the governed predictive discovery campaign for that priority.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #45 or Campaign #46 unless separately authorized.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #45 authorization.
