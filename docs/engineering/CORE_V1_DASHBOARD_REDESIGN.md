# Core v1 Dashboard Redesign — Staff Review and Build Plan

**Status:** Phase 0 authorized to start. Phases 1-2 sequenced, not yet started.
**Constraint (non-negotiable, confirmed by the CEO):** the dashboard
(`scripts/core_v1_dashboard.py`) must remain a **strictly read-only** layer over
already-logged data (`state.json`, the signals/fills/market-data logs,
`audit_report.json`). No write-back, no NAV restatement, no involvement in any
trading decision. This does not touch the One Rule (Core v1's frozen
parameters/weights/logic) — it was never in scope. Any implementation step that
would add a write path is out of scope and should stop, not be worked around.

## Why this exists

The dashboard was built solo, in a one-off session. The CEO asked for a
full-staff collaborative redesign for (a) usefulness and (b) efficiency to
read/understand. Six staff seats — CIO, Quant Researcher, Red Team, Risk/PM,
Ops/Compliance, Performance — reviewed the actual current dashboard code
independently on 2026-08-28 (parallel subagent calls, no seat saw another
seat's answer, per the org charter's independence rule). Chief of Staff
synthesized the six reviews below. This file is that synthesis plus the
resulting build plan, so a fresh Claude Code session (e.g. on the operator's
server) can pick this up without re-deriving it from scratch.

## Where things stood at review time

The current dashboard is real and read-only-safe — all six seats independently
confirmed no write-back paths exist. But two findings, each corroborated from a
different angle by multiple seats, matter more than any single seat's wishlist:

1. **The dashboard can currently assert more confidence than the evidence
   supports.** Red Team found the "System Healthy" banner renders green even
   when the independent price audit never ran (`audit_available == False`
   reads as non-failure, not as unverified), and that a *stale* audit only
   downgrades to a quiet "warn" tile even though that invalidates every NAV
   number rendered above it on the page. Ops/Compliance independently found
   the dashboard has zero indication of which git branch/commit produced the
   `state.json` it's rendering — which lands directly on a real fact this
   research thread discovered the same day: the live paper runtime
   (`itera-core-v1-paper.service`) runs off `gpt/core-v1-paper-runtime`, a
   branch this research thread has never reviewed, while this research
   branch (`claude/research-assessment-feedback-4auusg`) has never been
   deployed. The dashboard would show green regardless of that gap. This is
   the single most load-bearing bottleneck — everything else on the page is
   only trustworthy once you know which codebase produced it.
2. **The top of the page over-invests in narrative at the expense of
   substance.** Four of six seats (CIO, Quant Researcher, Ops, Performance),
   independently, flagged that the Portfolio Thesis prose and Market Regime
   hero card push each seat's actually-needed content down the page or off
   it entirely.

Six seats between them proposed roughly nine net-new panels. Shipping all of
them naively would directly fight the CEO's own stated goal (b) — efficient
to read. The build plan below resolves that tension by sequencing: fix
correctness first, cut noise second, add net-new by value/cost third.

## Needs-CEO item (separate from this build)

Ops/Compliance explicitly escalated this beyond "add a UI element": the live
paper runtime running off a branch nobody in this research thread has
reviewed is a fact for the CEO's decision, not staff's to quietly patch.
Phase 0 item 1 below fixes the *symptom* (you'll be able to see which branch
produced what you're looking at) — it does not resolve whether that branch
should be reviewed or reconciled. That's a separate, still-open decision.

## Build plan

### Phase 0 — fix what can currently mislead (do this first, regardless of anything else)

1. Runtime identity strip in the header: git branch + short SHA + full
   `state.json` path + hostname, sourced from a field the runtime writes into
   `state.json` at startup. (Ops/Compliance) — closes the branch-blind-spot.
2. Reorder so System Health / audit status renders *before* the NAV/PnL
   command deck, always. (Red Team + Ops/Compliance, independently convergent)
3. `audit_available == False` gets a visually distinct "UNVERIFIED" state —
   never nested inside the green "Healthy" banner. (Red Team)
4. A stale audit escalates to an explicit "numbers unverified" flag on the
   command deck itself, not a buried warn tile. (Red Team)
5. "Largest drift" gets its own informational-not-pass/fail caveat rendered
   in the UI, not just left as a code comment. (Red Team)
6. Full audit failure list surfaces (currently only `failures[0]` is shown,
   in both the top issues banner and the Price Audit health card). (Ops/Compliance)

### Phase 1 — cut noise (the 4-seat convergent finding)

7. Collapse the four accounting/diagnostics expanders (attribution table,
   sleeve table, fills/errors, Paper Data Export) under one off-by-default
   "Ops/Accounting Detail" disclosure. (CIO)
8. Reword Portfolio Thesis / Market Regime one-word labels to read as
   visibly interpretive, not fact-weighted. (Red Team + Quant Researcher)
9. Demote intraday P&L from a headline command-deck tile — sub-daily noise
   for a multi-day-horizon trend book. (Performance)

### Phase 2 — net-new panels, cheapest/highest-value first

10. **Decision Latency panel**, reusing `scripts/run_paper_runtime_cadence_audit.py`'s
    logic directly (bar-close → data-observed → signal → fill lag, per
    sleeve, fresh-bar-only framing) — cheapest to build since the logic
    already exists and was run for real against live data on 2026-08-28.
    (Quant Researcher)
11. **One combined Degradation-Band + Benchmark-Relative panel** — merges
    Risk/PM's ask (drawdown plotted against the pre-committed -26%/-35% band)
    with Performance's ask (Core v1 vs. Benchmark A/B on cumulative return,
    max drawdown, Calmar, annualized Sharpe, plus explicit T1-T4 trigger
    status) into a single panel serving both seats. **Must render only from
    already-governed artifacts** (`benchmark_metrics.json`, monthly letter
    outputs) — never compute Sharpe/Calmar live from raw logs in-page. That
    is the one place this phase could quietly drift into restating NAV; flag
    it explicitly to whoever implements this. (Risk/PM, Performance)
12. **Research Queue panel**, rendering `ops/campaign-log.md` / `ops/status.md`
    read-only: open campaign, its named-deficiency mapping, status. Lower
    urgency than the above. (CIO)
13. **Cross-sleeve correlation strip** — rolling correlation between the
    three crypto sleeves' returns, surfacing the tail-co-movement/concentration
    risk that's currently buried in the position grid. Heaviest net-new
    computation of the four; sequence last. Must be labeled diagnostic-only,
    not an actionable/rebalancing signal. (Risk/PM)

### Cross-cutting rule for every phase

Any performance number added anywhere on the page must carry an explicit
**LIVE** tag, visually distinguished from the frozen backtest ceiling
(~20% CAGR, Sharpe 1.34) per the org charter's backtest ceiling caveat.
CIO, Performance, and Red Team flagged this independently. This is not one
more panel — it's a constraint on every panel above that touches a number.
Red Team confirmed zero backtest CAGR/Sharpe references exist on the current
page (`grep -inE "sharpe|calmar|20%|1\.34"` returns nothing outside
comments) — keep it that way except where explicitly, visibly labeled LIVE
vs. the governed backtest figure.

## Verification before calling any phase done

- Re-run `grep -inE "sharpe|calmar|cagr"` against the dashboard file after
  Phase 2 item 11 ships — every match must sit inside an explicit LIVE-labeled
  context, never a bare number.
- Confirm no new code path writes to `state.json`, the logs, or
  `audit_report.json` — the dashboard's `read_json`/`read_jsonl` helpers
  should remain the only I/O.
- Have Red Team re-check the shipped Phase 0 specifically: does
  `audit_available == False` or a stale audit ever render inside a state
  that reads as "healthy" to a operator skimming the page in five seconds?
