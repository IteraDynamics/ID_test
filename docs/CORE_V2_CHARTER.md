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

Per the destination charter's recorded list, Core v2's founding work now addresses three of
Core v1's four named deficiencies, across two parallel campaigns:

1. **A single return source** (Campaign #53). Every Core v1 sleeve harvests trend. Campaign #53
   harvests a funding/carry premium — a structurally different return source, uncorrelated with
   directional price trend by construction.
2. **Single-name crypto** (Campaign #53). Core v1 trades BTC and ETH specifically. Campaign #53
   is cross-sectional across up to 19 liquid CDE perpetual-style instruments (confirmed
   2026-08-12, `docs/research/CAMPAIGN_53_SOURCE_FEASIBILITY_FINDING.md` §9).
3. **Structurally long-only** (Campaign #54, opened 2026-08-13). Core v1's six sleeves are all
   long-with-filter — able to step aside from a decline but never profit from one. Campaign #54
   evaluates `crash_short_v6`, an existing, unused, cross-asset-confirmed short sleeve, as a
   genuine diversifying return source rather than a defensive filter.

Not addressed by either founding campaign, and recorded here as an open avenue for later,
separate work: the absence of any rates/fixed-income sleeve. Zero existing raw material in this
repo touches that deficiency; it remains the most novel and most expensive avenue available.

## Founding campaigns

**Campaign #53 — cross-sectional funding carry on Coinbase Derivatives Exchange.**

- **Instrument and venue** (Amendment 5, resolved): CDE perpetual-style futures, the same venue
  this operator executes on. No cross-venue basis risk between research source and execution.
- **Mechanism:** delta-neutral funding harvesting — short the perpetual-style contract against
  spot (or the inverse) on whichever side collects the currently-signed funding rate. Native,
  same-venue `funding_rate` is directly observable per instrument, confirmed on an hourly
  interval across the full liquid cross-section.
- **Cross-section:** 19 liquid (>$1M/day) instruments as of 2026-08-12, spanning BTC and ETH
  down to smaller liquid names — real breadth for Amendment 1 power, not a handful of majors.
- **Status:** feasibility and the frozen specification (Section 3) are both drafted with no open
  items remaining. Not yet frozen — earliest possible freeze is 2026-08-14 per the campaign
  document's own one-day-minimum review rule. Derivatives eligibility on CDE remains an
  outstanding account-status item, blocking eventual execution but not specification work.

**Campaign #54 — macro-confirmed crash-short hedge sleeve.**

- **Instrument and venue:** BTC/ETH, short, same execution venue as Core v1's crypto sleeves.
  Shares Campaign #53's exact same derivatives-eligibility blocker.
- **Mechanism:** `crash_short_v6` exactly as coded, no perturbation — a seven-gate entry
  including cross-asset confirmation (SPY also below its own 175-day SMA) that distinguishes a
  macro bear from a crypto-only correction.
- **Status:** feasibility resolved; economic materiality measured directly (roughly -$2,000/yr
  expected return for roughly $2,000 shallower drawdown at $100k, one tested weight). Section 3
  (frozen specification) is drafted but explicitly incomplete — see its own document for why
  this family's power analysis is genuinely, honestly constrained by having effectively one
  historical crisis observation (2022), unlike Campaign #53's cross-sectional breadth.

Each campaign's own living document remains the authority on its own statistical design, gates,
and results. This charter does not duplicate or freeze either — it establishes that both are
Core v2 founding threads, developed in parallel, each addressing its own named deficiency, and
that Core v2 exists as a governed identity independent of any one campaign's result.

## Conditions this charter must keep satisfying

Per the destination charter's conditions on any successor, for both campaigns:

1. **Additive, not re-parameterised** — satisfied. Funding carry is a new return source, not a
   retuned Core v1 parameter; Campaign #54 evaluates inclusion of an existing fixed mechanism,
   explicitly not a parameter search (its own charter names this distinction directly, given the
   parameter-sensitivity pass's own findings about what a search looks like).
2. **Parallel, never replacing** — satisfied by this section.
3. **Same standards** — horizon feasibility, tradeability, and power analysis apply to both
   campaigns exactly as they would to any other; nothing about Core v2's status exempts either.
   Campaign #54's power constraint is a harder, more honestly-stated case, not an exemption.
4. **Floor risk unchanged** — satisfied by the funding boundary above.

## Not yet authorized

This charter authorizes documentation and planning only. It does not authorize:

- either campaign's specification execution, data acquisition beyond feasibility probing, or
  any frozen statistical design (both remain gated by `charter-campaign`'s own sequence and
  Amendment 3's one-document-per-campaign rule);
- a Core v2 runtime, paper account, or inception date — none is set; inception begins only once
  a specification exists and its own board transition authorizes it;
- any capital allocation, live or paper, to Core v2;
- any change to Core v1.

## Open items

**Campaign #53:**

1. Scoped to carry capture only (`docs/research/CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md`);
   directional conditioning and exposure gating, the charter's other two role hypotheses, are
   deferred as a separate future Core v1 overlay campaign, not part of Core v2.
2. Universe resolved: 10 of 19 liquid CDE perpetual-style names (BTC, ETH, XRP, SOL, HYPE, XLM,
   LINK, DOGE, ADA, DOT) via perp-vs-dated, satisfying Amendment 5 by construction; 4 more
   (`TEK`, `CHN`, `AIP`, `DEF`) confirmed equity-index products, out of scope; remaining 5
   (PAXG, ZEC, NEAR, ENA, ONDO) a documented future extension, not part of this specification.
3. Section 3 fully drafted, no open items. Earliest possible freeze 2026-08-14, per the
   document's own one-day-minimum review rule.
4. Power analysis plan-only pending data acquisition, itself pending the spec's freeze.

**Campaign #54:**

1. Section 3 drafted but explicitly incomplete: whether the 2020 COVID crash counts as a second,
   weaker macro-bear observation is unchecked; whether a broader crypto cross-section
   (reusing Campaign #53's already-resolved CDE universe) provides real corroboration or just
   restates the same single 2022 event is unresolved.
2. Power analysis cannot follow Campaign #53's cross-sectional route — this family's entire
   claim rests on one historical crisis. The charter states this plainly rather than forcing a
   false 50%-threshold pass; resolution is a judgment-bound decision, not a simulation output.

**Shared:**

Both campaigns are blocked on the same account-status item — derivatives eligibility on CDE —
outside either charter's scope to resolve.
