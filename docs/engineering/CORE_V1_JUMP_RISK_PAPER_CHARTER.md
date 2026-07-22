# Core v1 + Jump Risk Paper Integration — Engineering Charter

**Branch:** `feature/core-v1-jump-risk-paper`  
**Status:** Engineering integration  
**Research parameters frozen:** Yes  
**Live production promotion allowed:** No

## Objective

Operationalize the validated Jump Risk aligned-upside candidate alongside canonical Core v1 in paper trading without changing the existing baseline path.

This branch does not reopen research. It implements the frozen candidate approved in `docs/research/PROMOTION_DECISION_JUMP_RISK_V0.md`.

## Frozen Candidate

- overlay: `btc_eth_aligned_upside`
- risk quantile: 0.95
- boost scale: 1.15x
- decision cadence: hourly
- required implementation lag: one completed hourly bar
- direction source: canonical Core only
- standalone Jump Risk direction: prohibited

## Phase 1 — Mandatory Timing Audit

Before the overlay can be enabled, document and test:

1. market-data bar close timestamp,
2. data-ingestion completion time,
3. feature availability time,
4. model inference time,
5. Core position-state availability,
6. scale-decision time,
7. simulated order time,
8. governed return interval.

The implementation must prove that every input used by the decision was available before the simulated order timestamp.

## Phase 2 — Runtime Module

Build a deterministic Jump Risk paper module that:

- loads frozen model definitions,
- produces BTC and ETH medium/extended upside probabilities,
- computes training-distribution thresholds without lookahead,
- confirms Core directional alignment,
- emits a 1.00x or 1.15x scale,
- never creates a position when Core has none,
- never reverses Core direction,
- fails closed to 1.00x on missing or stale inputs.

## Phase 3 — Parallel Paper Paths

Maintain two simultaneous accounting paths:

- `core_v1_baseline`
- `core_v1_jump_risk_candidate`

The baseline must remain byte-for-byte behaviorally unchanged. Candidate performance must be attributable to incremental Jump Risk scaling and incremental costs.

## Phase 4 — Configuration and Safety

Required controls:

- feature flag disabled by default,
- explicit paper-only guard,
- immediate rollback to baseline,
- stale-data rejection,
- model/config fingerprint validation,
- maximum scale hard cap of 1.15x,
- no production-capital routing.

## Phase 5 — Telemetry

Each decision cycle must record:

- source timestamps,
- probability by asset and horizon,
- active training threshold,
- Core alignment state,
- chosen scale,
- reason code,
- incremental notional,
- estimated incremental cost,
- baseline NAV,
- candidate NAV,
- incremental P&L,
- runtime latency,
- data freshness.

## Phase 6 — Dashboard and Observation

Dashboard views should show:

- baseline versus candidate NAV,
- cumulative incremental P&L,
- active boost state by asset,
- action frequency,
- realized cost estimate,
- timing/freshness health,
- current model and configuration fingerprints.

## Acceptance Criteria

Paper activation requires:

- timing audit PASS,
- deterministic replay PASS,
- baseline parity PASS,
- stale/missing-data fail-closed tests PASS,
- no standalone direction tests PASS,
- telemetry completeness PASS,
- rollback test PASS.

## Paper Observation Policy

Paper observation is evidence gathering, not automatic promotion. A future production decision must evaluate:

- forward action frequency,
- realized timing feasibility,
- baseline/candidate divergence,
- incremental P&L after costs,
- stability across market regimes,
- operational incidents,
- calibration drift.

## Prohibited Changes

This branch must not:

- retune risk quantile,
- retune boost scale,
- alter model horizons or feature families,
- modify canonical Core directional rules,
- replace the baseline paper runtime,
- route live capital.

Any research change requires a new research charter and branch.