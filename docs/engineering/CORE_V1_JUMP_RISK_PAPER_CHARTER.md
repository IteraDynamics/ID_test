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
---

## Independent Audit Record — 2026-08-10

An independent audit was performed on the Jump Risk implementation before the timing audit was
run for the first time. Two material defects were found and corrected. Both were demonstrated
by execution, not asserted by inspection.

### F1 — Timing audit availability checks were tautologies (corrected)

`scripts/run_jump_risk_timing_audit.py` derived `source_bar_close` and `pnl_interval_start`
from the same expression (`action_bar_end - bar_delta`), so the check
`probability_available_before_pnl = source_bar_close <= pnl_interval_start` reduced to `X <= X`
and could never fail. `strictly_no_same_bar_source` reduced to `bar_delta > 0`, already
validated upstream. The same construction appeared in the overlay activation check. The
function never inspected the provenance of the probability series at all.

Demonstration: a prediction frame whose probability at bar `T` was taken from bar `T+5` — a
blatant five-bar lookahead — produced `availability_failures: 0`,
`same_bar_source_failures: 0`, `status: PASS`.

Correction:

- `_oos_probabilities` in `scripts/run_jump_risk_portfolio_integration.py` was split into
  `_oos_probabilities_unshifted` (indexed by the bar that produced each value) and
  `_oos_probabilities` (the actionable, shifted series). This is a pure refactor with no
  behavioral change.
- `verify_shift_provenance` establishes each served value's true source bar by comparing the
  served series against the pre-shift pipeline output. Source bars are now *derived from
  provenance*, never from arithmetic on the action timestamp.
- `shift_provenance_failures` was added to the check row and to the PASS criteria.
- The overlay activation check now consumes the verified provenance map.
- `lookahead_canary` runs a deliberately forward-shifted series through the same detector on
  every audit run and requires it to be rejected. An audit that cannot demonstrate a failure it
  would catch is not evidence; if the canary does not fire, the audit reports FAIL regardless
  of every other check.

No prior Jump Risk research result is invalidated by F1. The timing audit had never been
executed, so no result was published on the strength of it. The genuine lookahead protection —
the one-row shift — was present and correct throughout; it was simply never verified.

### F2 — Replay digest verification failed open (corrected)

`runtime/core_v1/jump_risk_replay_provider.py` skipped integrity verification entirely when a
replay artifact carried no `decision_digest`, even with `verify_digests=True`. Demonstration: a
report with the field omitted loaded clean; a wrong digest was correctly rejected. A missing
digest now raises. `require_digests=False` remains available as an explicit opt-out for fixture
construction. The in-repo artifact builder (`scripts/run_core_v1_jump_risk_replay.py`) has
always written digests, so no existing artifact is affected.

### Also corrected

- `config_fingerprint()` reported the module default `MAX_INPUT_AGE_SECONDS` even when
  `decide_asset_scale` was called with an override, so a decision could be labelled with a
  configuration it did not use. The effective bound is now part of the fingerprint and is
  propagated through every fail-closed branch.
- `tests/test_historical_regime_transition_discovery.py` asserted HC3 reconciliation within
  `5e-12`; observed BLAS drift on numpy 2.4 is ~5.6e-12. Tolerance loosened to `1e-9`. The
  frozen fixture values are unchanged; this is version robustness, not a result change.

### Found and deliberately NOT corrected — governed decisions required

These are recorded as known limitations. Changing them would change published results, so they
require a governed decision rather than a silent fix.

1. **No purge/embargo at the train/test boundary.** In `_oos_probabilities`, training rows
   within `horizon_bars` of a year boundary carry labels that extend into the test year — up to
   120 hours for the extended-up model. This is standard label leakage at fold edges. It
   inflates in-sample fit and may bias the train-derived threshold. Correcting it would change
   every Jump Risk probability and threshold, and therefore every downstream result.
2. **Overlay freshness is measured from `computed_at`, never from `source_bar_ts`.** A
   freshly-computed score over a stale bar passes the freshness gate. Bounded in practice by
   the replay provider's construction, unbounded in principle. A bar-age bound would be a
   behavioral change to a frozen candidate.

Neither limitation blocks the timing audit from running or from being trusted for what it now
measures. Both should be resolved before any live-capital decision.

### Test evidence

- new: `tests/test_jump_risk_timing_audit.py` — 7 tests, including a regression test pinning
  the exact five-bar-lookahead frame that previously passed and now fails;
- extended: `tests/test_core_v1_jump_risk_replay_provider.py` — missing-digest fail-closed,
  explicit opt-out, fingerprint sensitivity;
- Jump Risk suite: 22 passing; audit + provider + regime discovery: 42 passing.

### Status

Phases 1–2 and most of Phase 4 of this charter are implemented. The timing audit is corrected
but **has not yet been executed against canonical data**. Paper activation remains blocked in
`PARITY_BASELINE_ONLY` mode and is not authorized by this audit.
