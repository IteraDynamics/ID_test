# Itera Destination Charter

## Purpose

This charter records the firm's strategic destination decision of 2026-08-06. It governs how
research effort, risk, and calendar time are allocated between the two selected paths. It is a
strategy document: it authorizes no runtime, portfolio, order, exposure, or production change by
itself.

## Decision

Itera pursues two paths simultaneously, with an explicit asymmetry:

- **Path 1 — The Floor.** Core v1 operates as a personal wealth-building beta book: a
  diversified, trend-filtered portfolio run with fiduciary discipline. Its purpose is robust
  compounding and capital protection. It is judged against registered benchmarks
  (`docs/research/CORE_V1_LIVE_BENCHMARK_REGISTRATION.md`) and pre-committed expectations
  (`docs/research/CORE_V1_LIVE_EXPECTATION_AND_DEGRADATION_BAND.md`), not against its backtest.
- **Path 2 — The Moonshot.** The live record, the governance corpus, and one or more
  differentiated signals are developed into a due-diligence-grade track record aimed at outside
  capital (prop allocation, seeding, or equivalent). Path 2 is funded with research hours and
  overlay-sized risk only.

A revenue/product path (signals service) was considered and explicitly not selected.

## The One Rule

**The moonshot never touches the floor.**

1. Core v1 may change only through the full existing governance process. No Path 2 deadline,
   experiment, or ambition is grounds for modifying, retuning, or pausing the floor.
2. Overlays and new signals must be sized so that their total failure cannot materially damage
   floor outcomes.
3. The paper NAV series with inception 2026-07-07 is a permanent record. It must never be reset,
   restated, backfilled, or contaminated. Overlay variants run alongside the canonical baseline,
   never in place of it.

## Work-type taxonomy

All Path 1/Path 2 work is classified before scheduling:

- **Build-bound** — code, specs, runners, data fetchers. Executes at development velocity.
- **Clock-bound** — track-record accumulation, forward confirmation samples, live operational
  evidence. Accrues at one calendar month per month and cannot be compressed. Surplus velocity is
  spent widening parallel build work, never attempting to compress the clock.
- **Judgment-bound** — hypothesis selection, spec design, gate and multiplicity choices,
  result interpretation. Deliberately slowed: a specification may not be frozen in the same
  session it is first drafted.

## 90-day plan (from 2026-08-06)

Days 1–30 — lock the floor:

1. commit benchmark registration and degradation-band pre-commitments (this session);
2. ~~run the Core v1 frozen-parameter sensitivity pass (report-only, never retune)~~ — **CLOSED
   2026-08-12: no collapse on the 6 of 10 parameters the harness could exercise. Result and
   scope in `docs/research/CORE_V1_PARAMETER_SENSITIVITY_RESULT.md`. Direction resolved: see
   "Pending evidence" above.**
3. leave Core v1 otherwise untouched.

Days 31–60 — complete the pipeline once:

4. ~~finish the Jump Risk timing audit and enable the frozen overlay in paper~~ — **CLOSED
   2026-08-11: audits completed, candidate RETIRED as not deployable at runtime cadence. The
   pipeline was proven end to end, which was this item's structural purpose; the overlay itself
   is not enabled.**
5. build the governed funding/basis/open-interest data source (after board transition).

Days 61–90 — aim the machine:

6. adopt the standing research process amendments (`docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`);
7. progress Campaign #53 (funding carry) from charter toward a frozen, power-checked
   specification;
8. begin the monthly letter series (`docs/letters/`).

Months 4–12 — the clock runs: monthly letters accrue; surviving research flows through the
proven pipeline; a small real-capital allocation to Core v1 may be considered only after clean
operational evidence and only by separate decision; around month 12 the Path 2 package (letters,
record, differentiated signals, governance corpus) either exists and is shopped, or Path 1
continues having lost nothing.

## Authorization boundary

This charter authorizes documentation and planning work only. It does not authorize runtime,
strategy, order, execution, portfolio, NAV, exposure, threshold, model-training, or production
changes, nor any new campaign implementation before its own charter, specification, and board
transitions.

---

## Clarification to the One Rule — successor strategies (2026-08-11)

The One Rule has been read as "do not build something better than Core v1." That reading is
wrong and is corrected here.

**What the rule forbids: mutating Core v1.** Its parameters, weights, and logic are frozen
because a live record is only meaningful if the thing being measured stays fixed. Retuning
resets the record, invalidates the pre-registered degradation band, and repeats the selection
process that produced the original overfitting concern — on the same data.

**What the rule permits: building a successor in parallel.** A Core v2 developed as a separate
strategy, with its own charter, its own paper runtime, and its own inception date, costs Core v1
nothing. Both records accrue simultaneously and remain comparable. This is ordinary practice:
funds do not retune Fund I, they launch Fund II, and investors see both.

### Conditions on a successor

1. **Additive, not re-parameterised.** A successor must introduce a *named structural
   deficiency* it addresses. "I think we can do better" is not a research hypothesis. Changing
   SMA 175 to SMA 200 is retuning wearing a new name and is prohibited under this clarification
   as surely as editing Core v1 directly.
2. **Parallel, never replacing.** Core v1 continues untouched. A transition may only be
   considered after the successor has its own multi-year record, and is a separate governed
   decision.
3. **Same standards.** Horizon feasibility (Amendment 4), tradeability (Amendment 5), power
   analysis (Amendment 1), and pre-registration all apply.
4. **Floor risk unchanged.** Successor development is moonshot-bucket work funded with research
   hours, never with the floor's risk budget.

### Named deficiencies of Core v1 that would justify a successor

Recorded so that a future charter has a legitimate starting point rather than an impulse:

- **Structurally long-only.** All six sleeves are long-with-filter. The strategy can step aside
  from a decline but cannot profit from one.
- **A single return source.** Every sleeve harvests trend. Diversification is across assets, not
  across sources of return — there is no carry, value, or mean-reversion component.
- **No rates or fixed income.** The defensive state is cash.
- **Single-name crypto.** BTC and ETH specifically, rather than a cross-section, which the
  Campaign #53 feasibility work established is available on the operator's own venue.

These are architectural gaps addressable by adding return sources. None is a tuning problem, and
a successor charter built on any of them touches no Core v1 constant.

### Pending evidence

The Core v1 frozen-parameter sensitivity pass will inform which direction is legitimate. If
Sharpe holds across all perturbations, the design is robust and improvement cannot come from
parameters — only from added return sources. If it collapses on specific parameters, that is
itself a named deficiency and a legitimate successor charter item.

**Resolved 2026-08-12.** Full result: `docs/research/CORE_V1_PARAMETER_SENSITIVITY_RESULT.md`.
Of the ten perturbed constants, six were actually exercised by the harness; ΔSharpe on those six
ranged -0.022 to +0.039 against baseline 1.319 — no collapse, no knife edge. The other four were
provably inert in this harness (two by design, given how BTC macro state is injected into trend
sleeves; two due to a backtest-engine gap that discards one strategy branch's exposure target,
detailed in the result document). Under this section's own logic: **Sharpe holds. Improvement is
not available through retuning Core v1's parameters.** The legitimate direction is a successor
addressing a named structural deficiency (below), which Campaign #53 is already pursuing.

The backtest-engine gap found during this pass does not affect the live paper record — the live
runtime is unaffected and has run the strategy as coded since inception — but leaves an
unquantified, narrowly-scoped asterisk on the canonical backtest ceiling. See the result document
for scope; correcting it is a separate, not-yet-scheduled governed decision.
