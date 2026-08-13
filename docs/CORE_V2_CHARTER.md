# Core v2 Charter — DRAFT

## Status

**Draft, not frozen.** Per this repo's judgment-bound pacing convention — a specification may
not be frozen the same session it is first drafted (`docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`
Amendment 3) — this charter is written today and should not be treated as final until reviewed
on a later day. Nothing here authorizes data acquisition, runtime construction, capital
allocation, or any production behavior.

## Purpose

This is Core v2's own governing document, required by the successor clarification in
`docs/ITERA_DESTINATION_CHARTER.md` (2026-08-11): *"A Core v2 developed as a separate strategy,
with its own charter, its own paper runtime, and its own inception date, costs Core v1
nothing."* Core v1 remains frozen and untouched. This charter creates a second, independent
track — its own governance home, not a subsection of Campaign #53 or of Core v1's documents.

## Relationship to Core v1

Parallel, never replacing. The One Rule applies to Core v2's development exactly as it applies
to everything else at this firm:

- Core v1's parameters, weights, and logic are not touched by anything in this charter or by
  Core v2's development.
- Core v2 is funded with research hours and overlay-sized risk only, never the floor's capital
  or risk budget.
- A transition of capital from Core v1 to Core v2, if ever considered, is a separate governed
  decision requiring its own multi-year record — not in scope here and not anticipated for a
  long time.

## Named structural deficiency addressed

Per the destination charter's recorded list, Core v2's founding work addresses two of Core v1's
four named deficiencies at once:

1. **A single return source.** Every Core v1 sleeve harvests trend. Core v2's founding campaign
   harvests a funding/carry premium — a structurally different return source, uncorrelated with
   directional price trend by construction.
2. **Single-name crypto.** Core v1 trades BTC and ETH specifically. Core v2's founding campaign
   is cross-sectional across up to 19 liquid CDE perpetual-style instruments (confirmed
   2026-08-12, `docs/research/CAMPAIGN_53_SOURCE_FEASIBILITY_FINDING.md` §9).

Not addressed by this founding campaign, and recorded here as open avenues for later, separate
work under this same charter: structurally-long-only exposure in the directional sense (a
funding-carry position is market-neutral by construction, which is a different kind of answer
to this deficiency, not the trend-reversal answer the destination charter had in mind), and the
absence of any rates/fixed-income sleeve.

## Founding campaign

**Campaign #53 — cross-sectional funding carry on Coinbase Derivatives Exchange.**

- **Instrument and venue** (Amendment 5, resolved): CDE perpetual-style futures, the same venue
  this operator executes on. No cross-venue basis risk between research source and execution.
- **Mechanism:** delta-neutral funding harvesting — short the perpetual-style contract against
  spot (or the inverse) on whichever side collects the currently-signed funding rate. Native,
  same-venue `funding_rate` is directly observable per instrument, confirmed on an hourly
  interval across the full liquid cross-section.
- **Cross-section:** 19 liquid (>$1M/day) instruments as of 2026-08-12, spanning BTC and ETH
  down to smaller liquid names — real breadth for Amendment 1 power, not a handful of majors.
- **Status:** feasibility (venue, tradeability, funding-accrual, economic materiality) is
  resolved. Not yet chartered under the `charter-campaign` gate sequence to a frozen
  specification. Derivatives eligibility on CDE remains an outstanding account-status item,
  blocking eventual execution but not research or specification work.

Campaign #53's own living document (`docs/research/CAMPAIGN_53_SOURCE_FEASIBILITY_FINDING.md`,
and its eventual `docs/research/CAMPAIGN_53_<NAME>.md` per Amendment 3) remains the authority on
its own statistical design, gates, and results. This charter does not duplicate or freeze any of
that — it only establishes that Campaign #53's successful outcome is Core v2's founding
strategy, and that Core v2 exists as a governed identity independent of any one campaign's
result.

## Conditions this charter must keep satisfying

Per the destination charter's conditions on any successor:

1. **Additive, not re-parameterised** — satisfied; funding carry is a new return source, not a
   retuned Core v1 parameter.
2. **Parallel, never replacing** — satisfied by this section.
3. **Same standards** — horizon feasibility, tradeability, and power analysis apply to Campaign
   #53 exactly as they would to any other campaign; nothing about Core v2's status exempts it.
4. **Floor risk unchanged** — satisfied by the funding boundary above.

## Not yet authorized

This charter authorizes documentation and planning only. It does not authorize:

- Campaign #53 specification execution, data acquisition beyond feasibility probing, or any
  frozen statistical design (those remain gated by `charter-campaign`'s own sequence and
  Amendment 3's one-document-per-campaign rule);
- a Core v2 runtime, paper account, or inception date — none is set; inception begins only once
  a specification exists and its own board transition authorizes it;
- any capital allocation, live or paper, to Core v2;
- any change to Core v1.

## Open items

1. Campaign #53's Section 3 (frozen specification) is drafted, not frozen
   (`docs/research/CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md`) — scoped to carry capture
   only; directional conditioning and exposure gating, the charter's other two role hypotheses,
   are deferred as a separate future Core v1 overlay campaign, not part of Core v2.
2. Universe resolved 2026-08-13: 10 of 19 liquid perpetual-style names have a matched CDE
   dated contract (BTC, ETH, XRP, SOL, HYPE, XLM, LINK, DOGE, ADA, DOT) — perp-vs-dated on
   these 10 is the primary universe, satisfying Amendment 5 by construction. Four of the
   remaining 9 (`CDETEK`, `CDECHN`, `CDEAI`, `CDEDEF` root units) look like thematic/basket
   index perpetuals rather than single-asset contracts and may be the wrong instrument class
   for this design entirely — pending a `display_name` check before the spec freezes.
3. Power analysis is plan-only pending data acquisition, itself pending the spec's freeze.
4. Resolve derivatives eligibility on CDE — an account-status decision outside this charter's
   scope.
5. On a later-day review pass, confirm this charter's framing still holds before treating it as
   non-draft.
