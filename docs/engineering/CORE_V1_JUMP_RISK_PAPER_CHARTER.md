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

### F3 — Sleeve matrix reconciliation compared different units (corrected 2026-08-10)

`scripts/export_core_v1_canonical_sleeve_matrix.py` failed every fold with e.g.
`Fold 2020 matrix does not reconcile to fund NAV; max delta=1618.11`, blocking regeneration of
the Core WFO sleeve matrix that the timing audit depends on.

Cause: the captured `canonical_full_sleeve_equity_matrix.csv` is the *unscaled* alignment from
`run_core_v1_sleeve_contribution_audit.py:290` — sleeves start at allocated capital and the
frame includes the pre-OOS warm-up. The `stitched_fund_nav_from_sleeves.csv` written beside it
has already been rebased to starting capital (`:295-296`). The guard differenced the two
directly, so it failed by a constant factor even on sound data.

Evidence (fold 2020, via `scripts/diagnose_sleeve_matrix_reconciliation.py`):

- matrix sum at first common timestamp: `98,856.370179`
- fund NAV at first common timestamp: `100,000.000000`
- implied constant scale: `1.011568600167`
- pointwise ratio spread: `8.882e-16` (constant to machine precision)
- delta after rebasing: `5.8e-11`

Sleeve composition was intact throughout — six columns, exactly the Core v1 sleeves. This was a
units defect in the check, not corrupted data.

Correction: `reconcile_fold_matrix` rebases the matrix onto the NAV's basis before differencing
and retains the `1e-6` tolerance. The guard is not weakened: only a single global scale factor
is forgiven, and any genuine divergence in sleeve set, index, or composition makes the
matrix-to-NAV ratio non-constant and still fails. Covered by
`tests/test_sleeve_matrix_reconciliation.py` (6 tests), including a dropped sleeve and a
time-drifting composition, both of which must still raise.

---

## Timing Audit Result — 2026-08-10 (first execution)

Run: `artifacts/jump_risk_timing_audit/20260810T175016Z_jump-risk-timing-audit-v0`
Audit version: `jump_risk_timing_audit_v1` (post-correction).
Window: `2020-01-01 01:00` through `2025-12-30`, ~52,500 hourly rows per candidate.

### Status

- `status`: `STRUCTURAL_PASS_RUNTIME_CADENCE_PENDING`
- `structural_checks_passed`: `true`
- `lookahead_canary_passed`: `true`

All 8 candidates (BTC and ETH x immediate_any, immediate_down, medium_up, extended_up) returned
zero failures on every criterion: `shift_provenance_failures`, `availability_failures`,
`same_bar_source_failures`, `backwards_or_duplicate_timestamps`,
`gaps_shorter_than_expected_bar`, and both non-finite checks. Both overlay activation checks
(BTC, ETH) returned `unverified_source_rows: 0` and `timing_failures: 0`.

This is the first execution of this audit. Under the previous implementation the availability
checks were tautologies and could not have failed; this result is the first evidence that the
one-row shift is genuinely present and that every served probability traces to a strictly
earlier source bar.

### Overlay activation frequency

- BTC: `3,410` active hours = **6.49%** of the window
- ETH: `4,632` active hours = **8.81%** of the window

The overlay is selective rather than near-constant. This materially distinguishes the mapping
from undifferentiated leverage: a boost engaging under 10% of hours cannot be replicated by a
static 1.15x exposure. This is a descriptive finding, not a performance claim.

### Candidate firing rates against the 0.95 train quantile

| Asset | Candidate | Model | Firing rate |
|---|---|---|---:|
| BTC | immediate_any | gbm | 2.64% |
| BTC | immediate_down | logistic | 3.78% |
| BTC | medium_up | gbm | 6.35% |
| BTC | extended_up | logistic | 6.62% |
| ETH | immediate_any | gbm | 3.27% |
| ETH | immediate_down | logistic | 3.45% |
| ETH | medium_up | gbm | 11.08% |
| ETH | extended_up | logistic | 9.57% |

A 0.95 train-derived threshold implies ~5% nominal firing if the out-of-sample probability
distribution matched the training distribution. The immediate candidates fire *below* nominal;
the ETH medium/extended candidates fire at roughly twice nominal. This is evidence of
out-of-sample distribution shift in the probability scale, not of a timing defect. It is
recorded as an open calibration question: threshold behavior derived from training quantiles
does not transfer cleanly, most notably on ETH.

### Canary coverage — a documented limitation of the provenance check

The canary detects injected lookahead at materially different rates by model family:

| Model family | Candidates | Detection rate |
|---|---|---:|
| logistic | immediate_down, extended_up | 99.6% – 100% |
| gbm | immediate_any, medium_up | 57.1% – 78.8% |

The cause is value ties. Gradient-boosted outputs are piecewise constant, so adjacent bars
frequently carry identical probabilities; where consecutive values tie, a one-row shift is
undetectable by value comparison. The same blind spot applies to the primary
`shift_provenance_failures` check.

Consequence, stated precisely: the zero-failure result is strong evidence, not proof. For the
weakest case (BTC `immediate_any`) at least `29,994` rows are individually discriminating and
all passed. For the logistic candidates coverage is effectively complete. The overlay's own
inputs are `medium_up` (gbm, 65.6%/78.8% coverage) and `extended_up` (logistic, ~99.8%
coverage), so the mapping that would actually run is well covered in aggregate.

Closing this gap would require comparing source-bar identity rather than value equality — a
stronger check available if the pipeline is ever refactored to carry provenance columns.

### What this authorizes

Phase 1 structural timing only. Explicitly NOT authorized or established:

1. **Live runtime cadence.** The audit proves historical bar alignment. It does not measure the
   paper runtime's actual data-finalization, cycle-start, order-generation, and fill timestamps.
   Charter Phase 1 items 1-8 remain open and require live measurement.
2. **Purge/embargo.** Train/test fold-boundary label leakage remains untested and is the larger
   outstanding threat to the underlying AUC figures. Unchanged from the 2026-08-10 audit record.
3. **Paper activation.** The runtime remains `PARITY_BASELINE_ONLY`. Phases 5 and 6 (telemetry,
   dashboard baseline-vs-candidate views) precede any gate change.

---

## Live Runtime Cadence Audit — 2026-08-10

Run: `artifacts/paper_runtime_cadence_audit`, over 808 logged cycles (2026-07-07 to
2026-08-10). Measured from logs the runtime already writes; no runtime change.

This closes the promotion decision's blocking condition: *"Paper integration is blocked unless
the runtime can reproduce the research timing without using information unavailable at the
decision point."* The relevant research assumption is that the scale is actionable at source-bar
close and applies to P&L over the immediately following hourly interval.

### Result — FAIL against the research timing assumption

| Asset | Bar close to decision (median) | p95 | Within 1h assumption | Within 2h overlay gate |
|---|---:|---:|---:|---:|
| BTC | 6.00h | 7.82h | **0.00%** | **0.00%** |
| ETH | 3.01h | 7.66h | **0.00%** | 49.88% |

Zero of 808 cycles met the research timing assumption, for either asset.

### Per-sleeve observation lag

| Sleeve | Bar | Median age | p95 | Max | Bar periods |
|---|---:|---:|---:|---:|---:|
| ETH_1H_trend | 1h | 1.59h | 1.95h | 2.00h | 1.59 |
| BTC_4H_trend | 4h | 6.00h | 7.82h | 8.00h | 1.50 |
| ETH_4H_trend | 4h | 6.00h | 7.82h | 8.00h | 1.50 |
| SPY/QQQ/GLD/BIL | 1D | 40.80h | 85.87h | 95.92h | 1.70 |

The lag is structural, not incidental: every sleeve sits at roughly **1.5 to 1.7 bar periods**
behind its own bar close, across four different timeframes. Hourly polling against the last
*fully completed* bar produces a systematic one-bar lag plus polling phase. `ETH_1H_trend` —
the only hourly sleeve running live, and the closest available proxy for Jump Risk's data
cadence — is bounded in roughly `[1h, 2h]` and is never fresher than about one hour.

### Interpretation

The approved mapping requires BTC *and* ETH aligned upside. Under live cadence:

- BTC would fail the overlay's own 2h freshness gate on every observed cycle, pinning it to
  1.00x permanently;
- ETH would clear the gate roughly half the time, and never within the research assumption.

The promotion decision states the candidate's benefit "decays sharply after the first
implementation bar." The runtime is structurally at least one full bar late before Jump Risk
inference is even added. The +1.09pp CAGR / +0.082 Sharpe edge was measured at a one-bar
effective lag that this infrastructure does not achieve.

### Classification

`TIMING_GATE_FAILED — NOT DEPLOYABLE AT CURRENT RUNTIME CADENCE`

Paper activation remains blocked. This is a valid negative operational result, not an
implementation defect: the runtime is working as designed, and the design is one bar slower
than the research assumed.

### Note on a log artifact

Observe-to-decision latency computes as slightly negative (median -0.015s) because the cycle
summary in `signals.jsonl` is written marginally before the per-sleeve `market_data.jsonl`
rows. This is log write ordering, not negative latency. Internal runtime overhead is
sub-second and is not a contributing factor to the failure.

### Open decision

Three paths, none yet chosen:

1. **Re-specify at realistic lag.** Re-run the portfolio integration with the effective
   probability lag set to 2-3 bars instead of 1 (`_oos_probabilities` currently applies a
   single `shift(1)`), and observe what survives. This is the scientifically correct next test
   and is cheap. If the edge holds at realistic lag, the candidate can be re-chartered at that
   lag. If it does not, Jump Risk retires on evidence.
2. **Reduce runtime lag.** Investigate whether the one-bar lag is removable (bar-selection
   policy, polling frequency, provider availability). This is a change to the Core v1 floor and
   requires full governance under `docs/ITERA_DESTINATION_CHARTER.md`; it is engineering work
   in service of a modest edge.
3. **Retire Jump Risk** with this finding as the documented reason and redirect effort to
   Campaign #53.

No option is authorized by this audit.

### Correction, 2026-08-20 — the audit script had a measurement bug

`scripts/run_paper_runtime_cadence_audit.py` computed lag as `observed - bar_timestamp`
directly. `bar_timestamp` is a bar's *start* label, not its close
(`scripts/run_core_v1_paper_live.py`'s own `drop_incomplete_bars` docstring: "a bar labeled T
covers [T, T+bar_duration)") — the script never added the bar's own duration, so every lag
reported above was overstated by exactly that bar's period. A second, separate issue compounded
it for anything coarser than the hourly poll: a sleeve re-logs its current, unchanged bar on
every intervening cycle (correctly — nothing new has closed), and averaging those growing-stale
re-logs together with genuine fresh pickups inflated the aggregate further. Both are demonstrated
with regression tests in `tests/test_paper_runtime_cadence_audit.py`, including a canary
reproducing the exact original (buggy) numbers from the unfixed formula.

Re-run against the same underlying 808-cycle export, corrected script, two ways — "all
decisions" (every cycle, staleness of whatever bar is actually in hand) and "fresh bar only"
(the first cycle each bar was ever observed — true reaction speed to new information):

| Asset | All decisions (median) | Fresh bar only (median) | Fresh bar only p95 | Within 1h (fresh) | Within 2h gate (fresh) |
|---|---:|---:|---:|---:|---:|
| BTC | 2.00h | **0.60h** | 0.96h | **99.02%** | 99.51% |
| ETH | 0.81h | **0.59h** | 0.96h | **99.60%** | 99.90% |

Per sleeve, fresh-bar-only, all four timeframes cluster near the same absolute figure rather
than scaling with bar size — the "1.5-1.7 bar periods, consistent across timeframes" framing
above was itself an artifact of the bug, not a real property of the runtime:

| Sleeve | Bar | Fresh-pickup median | p95 | Max |
|---|---:|---:|---:|---:|
| ETH_1H_trend | 1h | 0.59h | 0.95h | 1.00h |
| BTC_4H_trend | 4h | 0.60h | 0.96h | 3.46h* |
| ETH_4H_trend | 4h | 0.60h | 0.96h | 3.46h* |
| SPY/QQQ/GLD/BIL | 1D | 0.53h | 0.94h | 1.13h |

\* the 3.46h max reflects one known ~12-hour outage gap in the underlying log, not typical
behavior.

**This does not itself overturn the Classification above or the Final Disposition below.** Two
caveats before either can be responsibly revisited:

1. BTC's figure is still a proxy through the wrong timeframe — there is no live BTC 1H sleeve
   (0% weight, not run per `scripts/run_core_v1_paper_live.py`'s own allocation), so BTC's
   fresh-pickup speed is measured via the 4H sleeve, not a direct hourly BTC signal. Fresh-pickup
   speed looks timeframe-independent across every sleeve measured here, which makes it a
   reasonable stand-in, but it is not the same as a direct measurement.
2. The "Lag Sensitivity Result and Final Disposition" section below explicitly cites this
   audit's old figure ("roughly 1.5-1.7 effective bars, which sits between rows 2 and 3") as
   part of its own reasoning for retirement. That citation is now factually wrong, and re-reading
   the lag-sensitivity table against the corrected figure is a separate, deliberate review this
   correction does not perform. Flagged at that section below, not resolved here.

---

## Lag Sensitivity Test — pre-registration (2026-08-10)

Recorded **before** the test was executed, per
`docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`.

### Question

The approved `btc_eth_aligned_upside` edge (+1.09pp CAGR, +0.082 Sharpe) was measured at an
effective one-bar implementation lag. The cadence audit established the live runtime operates
at roughly 1.5-1.7 bar periods. Does the edge survive at the lag this infrastructure achieves?

### Method

`scripts/run_jump_risk_lag_sensitivity.py`. The frozen research path is untouched:
probabilities come from `_oos_probabilities` exactly as in the approved study, including its
one-bar shift. Additional lag is applied to the resulting scale series, which is equivalent to
acting L bars later on identical information. Effective lag 1 reproduces the approved study;
effective lags 3-4 span the observed live cadence.

### Pre-registered decision rule

The candidate survives at a given lag only if it still satisfies the **original** promotion
gate against unchanged Core:

`delta_sharpe > 0 AND delta_calmar > 0 AND delta_max_drawdown_pct >= 0 AND delta_cagr_pct >= -0.50`

These are the four conditions from the approved study, unchanged. They are not relaxed,
reweighted, or restated after seeing results.

### Pre-registered disposition

| Outcome | Disposition |
|---|---|
| Survives at effective lag >= 3 | Re-charter the candidate at the honest lag |
| Survives only at effective lag <= 2 | **Retire** — the edge is not reachable on this infrastructure |
| Fails at every lag, including lag 1 | Investigate reproduction before concluding anything |

That third row matters: effective lag 1 must reproduce the approved study's PASS. If it does
not, the discrepancy is a reproduction problem and no conclusion about lag may be drawn from
this run.

### Prior

Stated in advance for the record: the promotion decision documents that the benefit "decays
sharply after the first implementation bar," so survival at effective lag 3+ is considered
unlikely. This prior does not alter the decision rule.

---

## Lag Sensitivity Result and Final Disposition — 2026-08-11

Run: `artifacts/jump_risk_lag_sensitivity/20260811T132219Z_jump-risk-lag-sensitivity`

### Reproduction guard: SATISFIED

The pre-registration required that effective lag 1 reproduce the approved study before any
conclusion about lag could be drawn. It does, exactly:

| | CAGR | Sharpe | Calmar | Max DD |
|---|---:|---:|---:|---:|
| Approved study | 21.02% | 1.400 | 1.347 | -15.60% |
| Lag-1 row | 21.02% | 1.400 | 1.348 | -15.60% |

The table is therefore interpretable.

### Result

Core baseline: CAGR 19.93%, Sharpe 1.318, Calmar 1.208, Max DD -16.50%.

| Effective lag | CAGR | dCAGR | dSharpe | dCalmar | dMaxDD | Gate |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 21.02% | +1.09 | +0.082 | +0.140 | +0.90 | **PASS** |
| 2 | 19.95% | +0.02 | -0.013 | -0.006 | -0.10 | REJECT |
| 3 | 19.78% | -0.15 | -0.027 | -0.024 | -0.20 | REJECT |
| 4 | 19.80% | -0.13 | -0.027 | -0.027 | -0.26 | REJECT |
| 5 | 19.60% | -0.33 | -0.043 | -0.046 | -0.37 | REJECT |

Max surviving effective lag: **1**.

### Interpretation

The decay is a cliff, not a slope. **98% of the edge is gone by the second bar.** At lag 2 the
overlay is already marginally harmful on every risk-adjusted measure, and it stays mildly
negative thereafter. The promotion decision's warning that the benefit "decays sharply after
the first implementation bar" is now quantified: essentially the entire +1.09pp lives inside
the first hour after the source bar closes.

The 2026-08-10 cadence audit measured live runtime cadence at roughly 1.5-1.7 effective bars,
which sits between rows 2 and 3 of this table. There is no plausible reading of this result
under which the approved mapping is economically positive on this infrastructure.

**Correction, 2026-08-20: the "1.5-1.7 effective bars" figure this paragraph relies on was
measured by a script with a bug** (see the "Correction, 2026-08-20" subsection under the Live
Runtime Cadence Audit above) and has been re-measured at closer to **0.6 effective bars**
(fresh-bar-only, hourly sleeves) — nearer row 1 (PASS) than rows 2-3 (REJECT) of the table above.
This is not, by itself, a re-opening of this disposition: it is a correction to one input this
paragraph's reasoning used, flagged here so a future review starts from the right number rather
than repeating this citation. Revisiting FINAL DISPOSITION on the strength of this correction —
including re-confirming the BTC proxy caveat noted above and re-deriving what "effective lag"
the corrected figure actually implies for this specific lag-sensitivity table — is its own
deliberate governance decision, not made by this correction.

A secondary observation, recorded for future reference: a signal whose entire value expires
within one hour is characteristic of a very short-lived reaction effect. If this family is ever
revisited, the binding constraint is **latency, not modelling**. Better features or models
cannot recover an edge that has already decayed before the decision is made.

### FINAL DISPOSITION

**Jump Risk Engine v0 — RETIRED. Not deployable.**

- Predictive research: VALIDATED and unretracted (BTC ROC AUC 0.80, untuned ETH transfer 0.76).
- Timing provenance: VERIFIED — zero shift-provenance failures across 8 candidates, canary
  passed (2026-08-10).
- Portfolio value at research lag: PASS, reproduced exactly.
- Portfolio value at achievable lag: **REJECT**.
- Paper activation: **NOT AUTHORIZED. Permanently blocked under this charter.**

The runtime remains `PARITY_BASELINE_ONLY`. No Core v1, runtime, strategy, order, NAV, or
exposure change is authorized by this closure. The overlay code, provider, tests, and audits
remain in the repository as governed research artifacts; they are not to be enabled.

This is a valid negative operational result. The research was sound and was independently
verified free of lookahead. The infrastructure cannot act quickly enough to collect what the
research identified. Those are separate facts and both are now on the record.

### Reopening conditions

This disposition may only be revisited if runtime cadence is independently measured at an
effective lag of 1 bar or better. That would require a change to the Core v1 floor and is
governed by `docs/ITERA_DESTINATION_CHARTER.md`. No reopening is authorized by evidence about
the signal itself; the signal was never the problem.
