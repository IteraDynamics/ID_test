# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #46 — Full Historical Regime State Sequence

**Classification:** Research infrastructure; deterministic source-foundation and support-feasibility construction

**Status:** GOVERNED PREFLIGHT PASSED — focused Campaign #46 tests pass and corrected source preflight passes; canonical generation, two-run replay validation, full-suite validation, scope review, and publication remain authorized; predictive-return generation and Campaign #45 result testing remain unauthorized

**Working branch:** `agent/campaign-46-full-regime-state-source`

**Repository:** `IteraDynamics/ID_test`

**Governing specification:** `docs/research/FULL_HISTORICAL_REGIME_STATE_SEQUENCE.md`

**Specification freeze commit:** `e3e2fe0fcdf7a00cea53adcdb4bc4c62445cb785`

**Implementation handoff:** `docs/research/FULL_HISTORICAL_REGIME_STATE_SEQUENCE_IMPLEMENTATION_HANDOFF.md`

**Handoff commit:** `d5d240e4cf1400c1dec1071bf9644d6aedb3611d`

**Source-gap correction commits:**

- runner correction: `c606e2f19dab954a06bcee288971dfa181881e52`
- specification correction: `9be6f532920ff66693b652a5cec38ff26ce4425b`
- handoff correction: `98179f002c84ea334256e735e68d409a09b96dba`

## Immediate objective

Generate and govern a complete BTC hourly historical regime-state ledger and transition inventory from the existing immutable `BaselineRegimeEngine` and governed BTC hourly OHLCV source, then determine whether that source population can satisfy Campaign #45's frozen independent-support gates.

Campaign #46 generates no forward returns and makes no alpha claim.

## Exact research question

Can Itera reconstruct a complete, deterministic, leakage-safe BTC hourly regime-state and transition history that contains at least 20 chronologically independent non-`UNKNOWN` transitions overall and at least 5 in each of three chronological feasibility folds, without modifying regime logic or inspecting outcomes?

## Strategic contribution

Campaign #46 creates a canonical historical market-state ledger reusable across transition, duration, spacing, persistence, and clustering research. It resolves Campaign #45's source insufficiency without weakening support standards or treating overlapping collapse episodes as independent observations.

## Authorization

**Decision:** GO for Campaign #46 source-only implementation and canonical validation.

Authorized now:

- maintain the frozen source-only module, runner, and focused tests;
- validate the governed BTC source and immutable classifier defaults;
- generate the complete state sequence, state runs, and transition inventory;
- calculate only source-support feasibility counts under the frozen 168-hour purge;
- generate canonical source artifacts twice and verify byte identity;
- verify LF-only text, strict JSON, source immutability, and full-suite compatibility;
- publish canonical Campaign #46 artifacts after all gates pass.

Not authorized:

- forward-return construction or inspection;
- predictive coefficients, p-values, effect sizes, direction tests, or candidate ranking;
- Campaign #45 estimator activation;
- changes to `BaselineRegimeEngine`, regime labels, thresholds, or classifier defaults;
- model training, replacement, or recalibration;
- signals, strategy changes, orders, execution, portfolio construction, NAV, exposure, or dashboard changes;
- production or paper-runtime integration.

## Frozen source and classifier

### BTC hourly source

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`
- byte count: `4,792,028`
- rows: `70,069`
- schema: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- timestamps: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`
- exact matching only; no interpolation, filling, resampling, nearest-row, as-of matching, or source substitution.

### Corrected governed gap evidence

The exact source identity above did not change. Governed preflight initially failed closed because the earlier documentation claimed 30 missing hourly timestamps. A deterministic full-source diagnostic established:

- discontinuities: `14`
- missing hourly timestamps: `36`
- largest elapsed interval: `16` hours
- largest missing block: `15` timestamps

The old value of `30` is superseded. This pre-result correction changes source metadata only. It does not change the source, classifier, state logic, transition logic, purge rule, folds, support gates, or predictive authorization.

### Regime classifier

- file: `research/regimes/baseline_engine.py`
- class: `BaselineRegimeEngine`
- method: `classify_dataframe()`
- instantiate with constructor defaults only.

The classifier file and defaults are immutable Campaign #46 inputs. Any disagreement fails closed.

## Preflight evidence

Focused suite executed locally on July 28, 2026:

- command: `python -m pytest -q tests/test_full_historical_regime_state_sequence.py`
- result: `10 passed`

Governed preflight executed locally after the source-gap correction:

- command: `python scripts/run_full_historical_regime_state_sequence.py --preflight-only`
- status: `PASS`
- source rows: `70,069`
- first timestamp: `2018-01-01 00:00:00`
- last timestamp: `2025-12-31 00:00:00`
- discontinuities: `14`
- missing hourly timestamps: `36`
- largest elapsed interval: `16`
- largest missing block: `15`

No canonical Campaign #46 artifacts or predictive outcomes had been generated when this evidence was recorded.

## Frozen outputs

Under `artifacts/full_historical_regime_state_sequence/`:

- `btc_hourly_regime_state_sequence.csv`
- `btc_hourly_regime_state_sequence.json`
- `btc_hourly_regime_state_runs.csv`
- `btc_hourly_regime_transitions.csv`
- `btc_hourly_regime_transitions.json`
- `btc_hourly_regime_support_feasibility.json`
- `btc_hourly_regime_state_report.md`
- `btc_hourly_regime_state_manifest.json`

## Campaign #45 feasibility gate

Campaign #46 reports, without outcomes:

- total non-`UNKNOWN` transitions;
- exact duplicate-anchor validation;
- deterministic transition set purged by at least 168 exact hours;
- three chronological feasibility-fold counts;
- whether purged overall support is at least 20;
- whether each fold has at least 5.

Feasibility status is one of:

1. `SOURCE_INVALID`
2. `INSUFFICIENT_OVERALL_SUPPORT`
3. `INSUFFICIENT_FOLD_SUPPORT`
4. `CAMPAIGN_45_SOURCE_FEASIBLE`

No predictive meaning may be attached to this status.

## Governing constraints

All work must remain deterministic, replay-safe, research-only, observation-only, anchor-local, fail-closed, and independent of production runtime state mutation.

No threshold, signal, order, execution, portfolio, NAV, exposure, model, strategy, or dashboard change is authorized.

## Authorized file surfaces

Campaign #46 may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`
- `docs/research/FULL_HISTORICAL_REGIME_STATE_SEQUENCE.md`
- `docs/research/FULL_HISTORICAL_REGIME_STATE_SEQUENCE_IMPLEMENTATION_HANDOFF.md`
- `research/ml/validation/full_historical_regime_state_sequence.py`
- `scripts/run_full_historical_regime_state_sequence.py`
- `tests/test_full_historical_regime_state_sequence.py`
- `artifacts/full_historical_regime_state_sequence/**`

No modification to the regime engine, regime contracts, runtime, strategies, allocation, execution, portfolio, NAV, exposure, or dashboards is authorized.

## Acceptance gates

1. Specification and handoff predate implementation-result inspection. **Passed.**
2. Corrected source identity, schema, timestamps, gap evidence, classifier interface, defaults, and labels pass preflight. **Passed.**
3. Focused Campaign #46 tests pass. **Passed: 10 passed.**
4. State rows reconcile one-to-one to all 70,069 source rows. **Pending canonical generation.**
5. State runs and transitions reconcile exactly. **Pending canonical generation.**
6. `UNKNOWN` rows and transitions remain visible and are excluded only from Campaign #45 feasibility. **Pending canonical generation.**
7. Deterministic 168-hour purge and three-fold allocation reconcile. **Pending canonical generation.**
8. No forward outcomes or predictive metrics are generated or inspected. **Must remain true.**
9. Two governed runs produce byte-identical canonical outputs. **Pending.**
10. Canonical text outputs are LF-only and JSON is strict. **Pending.**
11. Governed sources remain unchanged before and after generation. **Pending.**
12. Full repository suite passes with no new failures. **Pending.**
13. Scope review finds no production, runtime, model-training, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, or dashboard changes. **Must remain true.**

## Immediate sequence

1. Freeze Campaign #46 specification. **Completed.**
2. Freeze implementation handoff. **Completed.**
3. Record source-only implementation GO. **Completed.**
4. Implement source builder and focused tests. **Completed.**
5. Run governed preflight. **Completed: PASS after pre-result gap-evidence correction.**
6. Generate canonical artifacts. **Authorized next.**
7. Reproduce canonical artifacts in a second clean run and verify byte identity. **Pending.**
8. Run full repository suite and scope review. **Pending.**
9. Inspect only source-support feasibility status. **Pending.**
10. If feasible, return to Campaign #45 for a separate predictive implementation GO. If infeasible, close Campaign #45 or govern a longer source. **Pending.**

## Suspended Campaign #45

Campaign #45 — Historical Regime State and Transition Discovery remains suspended.

Its collapse-only population contains 14 independent event families against a frozen minimum of 20. No predictive returns, coefficients, p-values, rankings, or canonical Campaign #45 results have been generated or inspected.

Campaign #45's specification and support gates remain unchanged. Campaign #46 does not authorize Campaign #45 predictive testing.

## Campaign #44 priority context

Campaign #44 ranked:

1. S-002 — Historical regime state and transition structure: 29
2. S-003 — Historical event persistence, clustering, duration, and spacing: 27
3. S-008 — Simple BTC price-state baselines: 26
4. S-001 — Registered Core v1 collapse structure candidate A-001: 26

Campaign #46 is source infrastructure required to test S-002 responsibly.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #46.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #46 authorization.
