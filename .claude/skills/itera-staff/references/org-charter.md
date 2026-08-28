# Itera Dynamics — Org Charter

## The One Rule

Core v1's parameters, weights, and logic are frozen and never retuned. A
live record is only meaningful if the measured thing stays fixed.

A successor (Core v2) is allowed, but only if it addresses a **named
structural deficiency**, not a reparameterization of existing logic. The
named deficiencies:

1. Structurally long-only
2. Single return source (pure trend)
3. No rates/fixed-income exposure
4. Single-name crypto concentration (BTC/ETH only)

Any candidate, however good, that doesn't map to one of these four is not
a reason to touch Core v1 and is not automatically a reason to add
complexity to Core v2 either — it needs its own justification.

## Backtest ceiling caveat

Every backtest result is a selection-biased ceiling, not an expectation.
State both numbers when reporting a candidate: the backtest figure, and
the realistic live expectation (haircut for selection bias, execution
cost, and regime change). Never let a headline backtest number stand alone
in a briefing without this caveat attached.

## Org chart

```
CEO (founder/principal)
   │  sets mandate, owns capital-risk sign-off, resolves forks
   │
   ├── Chief of Staff — CEO interface. Briefing prep, log maintenance,
   │   triage/routing. Reports to CEO.
   │
   ├── CIO / Head of Research — translates mandate into chartered
   │   campaigns, prioritizes the queue, directs Quant Researcher,
   │   packages results into recommendations.
   │       │
   │       └── Quant Researcher — executes campaigns to the standing
   │           statistical bar. Reports to CIO.
   │
   ├── Red Team (independent of CIO/Quant) — mandatory gate before any
   │   candidate is called "alive." Can kill outright. Reports directly
   │   to CEO on disagreement, not routed through CIO.
   │
   ├── Risk / Portfolio Manager (independent) — portfolio-level fit:
   │   correlation, sizing, drawdown budget, Core v2 composition review.
   │   Only reviews candidates that already passed Red Team.
   │
   ├── Ops / Compliance (independent) — account approvals, venue and
   │   jurisdiction constraints, execution feasibility. Reports blockers
   │   directly to CEO.
   │
   └── Performance / Reporting (independent) — NAV, Sharpe/Calmar
       decomposition, the institutional-grade case. Reports directly to
       CEO, unfiltered by the seats it grades.
```

Independence matters structurally, not just nominally: Red Team, Risk/PM,
Ops, and Performance do not report through CIO. If any of these are
folded into the CIO's own reasoning, the mandatory gate becomes theater —
the same context that wants a result to work is being asked to fail it.

## Escalation matrix

| Decision type | Who decides | 
|---|---|
| Kill a campaign on a clean, well-powered null | Quant Researcher / CIO, logged | 
| Routine test design within an already-chartered priority | Quant Researcher | 
| Red Team pass/fail on a candidate | Red Team, alone — cannot be overridden by CIO | 
| Charter a new research direction | CEO approval required | 
| Anything touching Core v2 composition or weights | CEO approval required | 
| Any capital deployment decision | CEO approval required | 
| Genuine fork where staff disagree | Escalate to CEO — name the fork, don't average it away | 
| Any proposed change to Core v1's live logic, weights, or parameters | **Never** — automatic hard stop regardless of staff consensus |

## Known state as of last full briefing (2026-08-28)

Keep this section current in `ops/status.md`, not here — this file is the
charter (rules), not the log (state). If you're reading this file for
current status instead of `ops/status.md`, you're in the wrong file.
