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
- **Cross-section:** 19 liquid (>$1M/day) instruments identified 2026-08-12, spanning BTC and
  ETH down to smaller liquid names — but see Status below: only BTC and ETH are in this
  specification's actual execution scope as of 2026-08-14, the other 8 deferred, not part of the
  original 10-name cross-sectional breadth this line originally described.
- **Status:** CDE's crypto perpetual-style contracts turned out to be only ~13 months old
  (confirmed by direct probe, not assumption), breaking the frozen Charter's multi-year history
  assumption. **Decided 2026-08-14, in two parts:** (1) discovery runs on Deribit's multi-year
  funding history, confirmation on CDE's native ~13-month data, per Amendment 5's explicit
  allowance for differing source/execution venues; (2) Deribit turned out to list perpetuals for
  only 2 of the 10 candidate names (BTC, ETH — confirmed genuine absence for the other 8, not a
  query failure), so those two proceed under the decided design now, while the other 8 are
  deferred — neither excluded nor downgraded to a permanent lower standard — until CDE's own
  native history is long enough to support them without a proxy venue. How long that takes is
  not decided; it is a future judgment call. Not frozen — see the campaign document's own §3a-i.
  Derivatives eligibility on CDE is **resolved as of 2026-08-14** — approved. Execution still
  requires the frozen specification and its own board transition, neither of which this
  resolution grants on its own.

**Campaign #54 — macro-confirmed crash-short hedge sleeve.**

- **Instrument and venue:** BTC/ETH, short, same execution venue as Core v1's crypto sleeves.
  Shares Campaign #53's exact same derivatives-eligibility blocker.
- **Mechanism:** `crash_short_v6` exactly as coded, no perturbation — a seven-gate entry
  including cross-asset confirmation (SPY also below its own 175-day SMA) that distinguishes a
  macro bear from a crypto-only correction.
- **Status:** feasibility resolved; economic materiality measured (roughly -$2,000/yr expected
  return for roughly $2,000 shallower drawdown at $100k, one tested weight — flagged 2026-08-14
  as directionally right but not a reliable point estimate). Section 3 is drafted but explicitly
  incomplete: an adversarial review found the strategy's own cross-asset gate was very plausibly
  hand-built by examining the same 2021/2022 episodes now cited as evidence it works, downgrading
  that evidence from independent confirmation to something closer to confirming the designer's
  own hindsight pattern-match. 2018 is the one regime observation not implicated by that design
  history and is now this campaign's most credible evidence. See the campaign document's own
  §3c and §4 for the full correction.

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
2. Universe originally resolved at 10 of 19 liquid CDE perpetual-style names (BTC, ETH, XRP,
   SOL, HYPE, XLM, LINK, DOGE, ADA, DOT) via perp-vs-dated; 4 more (`TEK`, `CHN`, `AIP`, `DEF`)
   confirmed equity-index products, out of scope; 5 (PAXG, ZEC, NEAR, ENA, ONDO) a documented
   future extension. **Narrowed again, 2026-08-14 (item 3 below): actual execution scope for
   this specification is BTC and ETH only**, the other 8 of the 10 deferred.
3. **Both history-depth questions resolved, decisions made, not left open.**
   `scripts/probe_cde_history_depth.py` confirmed CDE's own contracts are ~13 months old
   regardless of endpoint availability, breaking the frozen Charter's multi-year assumption.
   Decided: Deribit-for-discovery, CDE-for-confirmation (Amendment 5 permits this explicitly),
   over broadening the universe or cutting gates. Then `scripts/probe_deribit_universe_coverage.py`
   found Deribit lists perpetuals for only 2 of the 10 names (BTC, ETH — confirmed genuine
   absence for the other 8). Decided: BTC/ETH proceed now under the two-venue design; the other
   8 are deferred, not excluded and not downgraded to a permanent lower standard, until CDE's own
   native history is long enough on its own — a future judgment call, not fixed here.
5. **Both remaining design gaps closed, 2026-08-14.** Roll policy: roll N business days before
   expiry (N calibrated against CDE's own liquidity-migration data, not invented here), roll only
   into a confirmed successor contract (needs a live-account check before first use, not a
   research one), roll costs treated as recurring transaction costs, and each roll is a fresh
   entry decision rather than a mechanical continuation. Hybrid mechanism: the campaign's
   candidates now split into a **statistical family** (funding level, persistence, open interest
   — genuinely discovered, subject to FDR and Amendment 1 power) and a **structural family**
   (basis/calendar-spread — a mechanically-converging, cash-and-carry-style position whose
   validity rests on contract mechanics, evaluated against a cost threshold rather than pooled
   into the same statistical pipeline). Section 3's decision rule and Section 4's power plan were
   both revised to keep this split consistent throughout, not just noted in one place.
6. Power analysis plan-only pending data acquisition, itself pending the spec's freeze, and now
   scoped explicitly to the statistical family only. All design gaps ahead of freeze are closed;
   what remains is the same-day-edit pacing concern noted in Section 3's own status line and the
   review pass itself.

**Campaign #54:**

1. Section 3's 2020 and cross-sectional-corroboration questions are answered: 2020 confirmed as
   a real but unprofitable episode; 2018 (not previously considered) confirmed as a second real
   regime with a genuine profitable payoff.
2. **New finding, 2026-08-14 adversarial review:** the strongest-looking evidence — the SPY
   gate's 2021 rejections and the 2022 payoff — is plausibly circular. `crash_short_v6`'s own
   docstring shows its design was built by examining exactly these episodes. 2018 is the one
   observation not implicated and is now the campaign's most credible evidence; the others are
   real but weaker than previously stated. See the campaign document's own §3c.
3. Power analysis remains judgment-bound, now on a corrected reading: one clean payoff (2018),
   one likely-circular payoff (2022), one correctly-fired-but-unprofitable case (2020) — not the
   "two favorable of three" framing an earlier draft used.

**Shared:**

Derivatives eligibility on CDE — the one account-status item both campaigns shared — is
**resolved as of 2026-08-14**, approved for both at once as anticipated. Remaining open items are
research/specification work only (§3a-i's two design gaps for #53; the review-and-freeze pass for
both), not account status.
