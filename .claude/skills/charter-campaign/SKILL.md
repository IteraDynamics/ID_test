---
name: charter-campaign
description: Charter a new Itera research campaign. Walks the five standing amendments as sequential kill-gates — horizon feasibility, tradeability, economic materiality, statistical power, document format — before any specification is written. Use whenever a new research idea, candidate family, hypothesis, or campaign is proposed, or when asked whether an idea is worth pursuing.
---

# Chartering a campaign

A campaign charter is a series of **kill-gates, run in order**, each cheap, each capable of
ending the work before the expensive part begins. The gates exist because four of them have
each already killed or redirected real work here *after* the expensive part was done. That is
the failure mode this skill prevents.

Do not skip ahead to the interesting statistical design. The gates run in this order because
each one is cheaper than the one after it, and a failure at gate 1 makes gates 2–5 irrelevant.

Governing documents — read them, don't paraphrase from memory:

- `docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md` (the amendments themselves)
- `docs/ITERA_DESTINATION_CHARTER.md` (the One Rule, the named Core v1 deficiencies)
- `CLAUDE.md` (measured operating facts)

## Gate 0 — Is this a campaign or is it tuning?

Before anything else, answer: **what named structural deficiency does this address?**

"I think we can do better" is not a hypothesis. "Core v1 has no carry component" is. The
charter clarification of 2026-08-11 lists four named deficiencies of Core v1 — structurally
long-only, single return source, no rates/fixed income, single-name crypto. A campaign that
does not name a deficiency of this kind, and instead proposes different parameters for
something that already exists, is retuning and is prohibited. Say so plainly and stop.

Also state, in one sentence, **what result would falsify the hypothesis.** If no observable
outcome would cause abandonment, this is not research.

## Gate 1 — Horizon feasibility (Amendment 4)

The gate that retired Jump Risk after ~18 months of work.

1. State the **expected decay horizon** of the hypothesised effect: how long after the
   signalling event does it persist? Give a number with units.
2. State the **measured runtime cadence** for the bar size the campaign would use. Cite a dated
   cadence audit — `artifacts/paper_runtime_cadence_audit`, or re-run
   `scripts/run_paper_runtime_cadence_audit.py`. Never assume it.
3. State the **feasibility margin**: horizon ÷ cadence, and justify the factor.

Current measurement (2026-08-10, 808 cycles): ~1.5–1.7 bar periods behind bar close, across
1h, 4h and 1D alike.

**Rule of thumb from `docs/research/CANDIDATE_HORIZON_FEASIBILITY_SWEEP.md`:** a candidate that
consumes more than ~25% of its own horizon in decision lag is not worth chartering. The sweep
that applied this retroactively **inverted** the Trend Persistence ranking — the candidates
called the "central finding" were the infeasible ones. Rank candidates by feasibility before
looking at their statistics, not after.

If the margin fails: the charter stops here. Do not propose modelling improvements; no model
recovers an edge that expires before the order can be placed.

## Gate 2 — Tradeability (Amendment 5)

1. Name the **exact instrument** whose premium or effect would be harvested.
2. Name the **venue this operator can verifiably trade it on** — jurisdiction, account status,
   and regulatory restriction all checked, not assumed. US jurisdiction: Binance returns 451,
   Bybit 403.
3. State whether the **research data source and the execution venue are the same**. If they
   differ, the charter must say why the premium transfers, and the specification must include a
   cross-venue basis check.

Known trap, established in Campaign #53 feasibility: **CDE ≠ INTX.** Coinbase Derivatives
Exchange is the executable venue; Coinbase International is a different venue with different
products, and the Advanced Trade API's `PERPETUAL` filter returns only INTX. CDE lists its
perpetual-style contracts as very-long-dated `EXPIRING` futures (`BIP-20DEC30-CDE`). CDE also
publishes **no funding rate** through that endpoint.

Write a probe rather than reasoning from documentation. `scripts/probe_funding_data_sources.py`
and `scripts/probe_coinbase_derivatives_universe.py` are the pattern: public endpoints only,
read-only, findings written to `artifacts/`, and a report that never raises.

## Gate 3 — Economic materiality

Capital scale is ~$100k. Before designing anything, state the **expected dollar return per
year** at that scale under an optimistic-but-defensible effect size.

Every edge examined here so far has landed at roughly $400–1,500/yr. That is not a reason to
refuse the work, but it is a number the operator is entitled to see *before* committing weeks
to it, not after. State it plainly and without softening.

## Gate 4 — Power (Amendment 1)

Simulation-based, frozen with the specification:

1. a plausible effect-size grid with written justification (liquid-market ICs are ~0.02–0.05);
2. the simulated probability that a true effect of each size passes **every** frozen gate —
   support gates, sign gates, multiplicity, decision rules — given the frozen sample;
3. power at the central plausible effect size.

**Below 50% power, the campaign does not run.** The remedy is redesign before any outcome
exists: more data, a broader cross-section, fewer gates, or abandonment. Recording an
underpowered null as evidence is prohibited.

Prefer **cross-sectional** designs to time-series ones. A time-series test on autocorrelated
data has far fewer effective observations than rows; a cross-section of N instruments buys
power that no amount of history buys.

Multiplicity (Amendment 2): FDR or pre-registered top-k at discovery; the strict standard at
confirmation, on the untouched holdout only. A pipeline in which no plausible true effect could
ever reach the holdout fails Amendment 1 by construction.

## Gate 5 — Document format (Amendment 3)

One living document: `docs/research/CAMPAIGN_<N>_<NAME>.md`, sections appended and frozen in
order, each freeze a commit. Auxiliary evidence goes in `artifacts/`, never in extra prose.

Sections: Charter → Feasibility → Frozen specification → Power → Execution evidence → Result →
Closure.

**Pacing rule: a specification may not be frozen in the same session it is first drafted.** At
least one review pass on a later day. If asked to draft and freeze together, draft only and say
why.

## Writing the charter

Only after gates 0–5 pass. The Charter section states: the question, the mechanism (why this
effect should exist economically), why it is not already represented in Core v1, the
falsification statement, and the gate results above with their numbers.

## When a gate fails

Report the failure and stop. Do not propose a workaround that routes around the gate — that is
how eighteen months went into an unreachable signal. A failed gate is a cheap, successful
outcome: it is the skill working.
