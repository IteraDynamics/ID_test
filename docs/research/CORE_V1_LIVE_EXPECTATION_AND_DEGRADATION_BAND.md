# Core v1 — Live Expectation and Degradation Band

## Status

**PRE-COMMITTED — frozen 2026-08-06, before meaningful live record accrues.**

This document fixes, in advance, what live performance Core v1 is expected to deliver, what
range of outcomes is within plan, and what specific observations trigger a governed
re-evaluation. Its purpose is to prevent both failure modes of live monitoring: panicking at
normal noise, and rationalizing genuine decay.

## Honest statement of selection bias

Core v1's canonical backtest (approximately 20% CAGR, -17.5% maximum drawdown, Sharpe 1.34)
was produced by an iterative, pre-governance development process: multiple trend-following
generations (v1 through v11, including a grid of cap variants), several equity-filter versions
with episode-motivated amendments, and an allocation scenario comparison — all evaluated on
overlapping historical data without multiplicity correction. The backtest is therefore the
maximum of a substantial implicit search, over a historical window (circa 2019–2025) that was
favorable to every sleeve.

Accordingly:

- **the backtest Sharpe of 1.34 is declared a selection-biased ceiling, not an expectation;**
- the backtest maximum drawdown of -17.5% is declared a lower bound on plausible live drawdown.

## Live expectation band

- Expected live Sharpe (zero benchmark, multi-year horizon): **approximately 0.7 to 0.9**.
- Planning drawdown assumption: **1.5x to 2x the backtest maximum, i.e. roughly -26% to -35%**.
  A live drawdown of 20% is within plan and is not, by itself, evidence of failure.
- Expected behavior versus benchmarks: over multi-year horizons, canonical Core v1 should beat
  Benchmark A (static twin) on drawdown and Calmar; it is expected to lag Benchmark A on raw
  return during strong uninterrupted bull phases. That lag alone is within plan.

## Re-evaluation triggers

A governed re-evaluation is mandatory if any of the following occurs. Trigger observations are
assessed monthly at letter time; operational triggers are assessed immediately.

- **T1 — Drawdown beyond plan:** live drawdown exceeds 30% from peak NAV.
- **T2 — Persistent risk-adjusted failure:** with at least 12 months of live record, trailing
  12-month Sharpe is below 0.3 for three consecutive monthly readings.
- **T3 — Benchmark dominance:** Benchmark A beats canonical Core v1 on all three of return,
  maximum drawdown, and Calmar over a trailing 12-month window.
- **T4 — Operational integrity:** any unexplained replay mismatch, price-audit failure, or
  unexplained divergence between runtime state and reconstructed NAV. This trigger is
  immediate and takes precedence over all performance considerations.

## What a re-evaluation authorizes

A triggered re-evaluation authorizes exactly:

1. a documented review comparing live behavior against this document and the registered
   benchmarks;
2. a written finding: within-plan / degraded / operationally compromised;
3. if degraded or compromised — a decision among: continue with explicit acknowledgment, reduce
   or suspend paper allocation, or charter a new governed campaign to develop a successor.

A re-evaluation never authorizes in-place retuning of Core v1 parameters, retroactive
restatement of the record, or silent strategy substitution. Any successor strategy is a new
versioned strategy under full governance, and the Core v1 record closes rather than mutates.

## Within-plan outcomes (recorded to prevent future panic)

The following are expected at some point during a multi-year live record and do not trigger
re-evaluation by themselves: consecutive losing months; a 15–25% drawdown; a full year in which
Benchmark B (60% SPY / 40% cash) outperforms; whipsaw losses around SMA boundaries in choppy
regimes; extended flat periods with high cash allocation while trend filters are defensive.

## Authorization boundary

This document authorizes monitoring, reporting, and the re-evaluation procedure above. It does
not authorize any change to Core v1, the paper runtime, orders, exposure, NAV handling, or
production behavior.
