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
2. run the Core v1 frozen-parameter sensitivity pass (report-only, never retune);
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
