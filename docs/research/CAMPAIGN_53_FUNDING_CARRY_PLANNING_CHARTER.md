# Campaign #53 — Perpetual Funding and Basis Carry

## 1. Charter

### Status

**PLANNING CHARTER — campaign selection and source feasibility planning only.**

No Campaign #53 predictor, outcome, ranking, economic result, or runtime change is authorized
under this charter. Data acquisition requires a separate board transition recorded on
`docs/ITERA_CAMPAIGN_BOARD.md`.

Campaign #53 is the first campaign governed by
`docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`: it uses the single-document format, requires a
frozen power analysis before execution, and applies FDR-based discovery with strict
confirmation reserved for the untouched holdout.

### Question

> Do perpetual-futures funding rates and perp–spot basis contain information about subsequent
> BTC and ETH returns — as a carry premium, a positioning/crowding signal, or both — beyond
> what is already represented in Core v1's price-trend state?

### Economic mechanism

Perpetual funding is a recurring payment between longs and shorts that pins the perp to spot.
Persistent positive funding means leveraged longs are paying to hold exposure — simultaneously
a measurable carry stream to the other side and a direct gauge of crowded positioning.
Funding/basis carry is among the most persistent documented crypto-native premia, and it is
non-price information: nothing in Core v1's SMA/trend state observes it. This gives the family
a materially higher prior than recent price-derived candidates, and a plausible role as either
a directional conditioner or an exposure/risk governor for existing crypto sleeves.

### Why the historical record can test it

Major venues publish funding histories back to roughly 2019–2020 for BTC and ETH (8-hour
cadence on most venues), alongside open interest and mark/index prices for basis. This supports
a development/validation split with a meaningful untouched terminal holdout under the standard
holdout-first temporal architecture.

### Falsification statement

The family is falsified for its frozen design if, after FDR-controlled discovery on the
development interval and pre-registered confirmation on the untouched holdout, no funding- or
basis-derived candidate shows the pre-registered association with subsequent returns at the
frozen support and decision standards.

### Candidate-family sketch (to be frozen in the specification, not here)

- Signals: funding level, funding persistence/accumulation over trailing windows, basis level
  and change, open-interest change, and funding-conditioned interactions with existing trend
  state.
- Targets: forward BTC and ETH returns at horizons matched to the funding cadence (e.g. 8h
  multiples through roughly one week), with candidate breadth sized per Amendment 2 and power
  checked per Amendment 1.
- Role hypotheses: directional conditioning, exposure gating, and carry capture are distinct
  claims and will be separated in the frozen specification.

### Clarification — role scoped to carry capture (2026-08-13)

This section is frozen (single commit `ba57e6a`) and is not rewritten here; this is an append,
per Amendment 3.

The three role hypotheses above are not equivalent research subjects. **Carry capture** is a
standalone, delta-neutral position — it can be built, tested, and run as its own strategy with
its own runtime, independent of Core v1. **Directional conditioning** and **exposure gating**
are, by construction, modifications to how Core v1's *existing* crypto sleeves behave — an
overlay on Core v1, in the same shape as the retired Jump Risk Engine (built and gated
separately, never mutating the frozen baseline, enabled only through its own governed decision).

`docs/CORE_V2_CHARTER.md` (2026-08-13) requires Core v2 to be a standalone successor with "its
own charter, its own paper runtime, and its own inception date." Only carry capture fits that
description. **Core v2's founding specification is therefore scoped to carry capture only.**
Directional conditioning and exposure gating are not discarded — they remain legitimate,
separately chartered future work, structured as a Core v1 overlay (subject to the One Rule,
same as Jump Risk was) rather than folded into Core v2's frozen specification. Section 3 below
addresses carry capture exclusively.

### Clarification — cross-sectional universe vs. the frozen Question's wording (2026-08-14)

Found on adversarial review, not before: the frozen Question above asks specifically about
"subsequent BTC and ETH returns." The resolved specification (§3) targets a 10-name
cross-section — BTC and ETH among them, but also XRP, SOL, HYPE, XLM, LINK, DOGE, ADA, DOT. The
Question's original wording predates the CDE feasibility work and the resulting redirect toward
a cross-sectional design specifically because breadth is what a properly powered discovery stage
needs (Amendment 1). The cross-sectional design is the correct one and is not being revisited
here — but the Charter's own frozen wording no longer accurately describes what the
specification tests, and that mismatch should have been caught when the universe was resolved,
not left for a later review pass to find. Recorded as what it is: an oversight, corrected by
this append, not a redesign.

## 2. Feasibility (authorized planning work)

Authorized now, without generating research outcomes:

1. inventory candidate venues and endpoints for historical funding, open interest, and
   mark/index prices (public endpoints; no authentication or trading scope);
2. verify obtainable history depth, cadence, gaps, and revision behavior per venue for BTC and
   ETH perpetuals;
3. specify the governed acquisition design: extension of the existing snapshot pattern
   (`scripts/fetch_coinbase_hourly_history.py` and source manifests) to funding/OI/basis
   sources, with full provenance, hashes, missing-interval inventories, and fail-closed
   revision handling;
4. draft the temporal architecture (development / validation / untouched terminal holdout)
   contingent on verified coverage.

Not authorized until recorded board transitions: bulk data acquisition; predictor or outcome
computation; the frozen statistical specification's execution; any economic test; any runtime,
strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

### Feasibility — resolved (2026-08-11 to 2026-08-12)

The four planning items above are complete. Full detail, including two corrections made during
the work (a venue-classification error that hid the tradable CDE universe, and a probe reading
the wrong JSON field that produced a false "funding not published" conclusion), lives in
`docs/research/CAMPAIGN_53_SOURCE_FEASIBILITY_FINDING.md` — kept as a separate evidentiary
record rather than folded in here given its length and its own dated, append-only structure;
this is a narrower reading of Amendment 3's "auxiliary evidence lives in `artifacts/`" than the
letter of the rule, recorded honestly as such rather than silently.

Summary: execution venue is Coinbase Derivatives Exchange (CDE), the operator's actual venue —
not Coinbase International (INTX), a different product initially conflated with it. CDE lists
99 futures; 19 perpetual-style contracts trade above $1M/day. All 19 publish native, same-venue,
hourly `funding_rate` (confirmed 2026-08-12; the field lives at
`future_product_details.funding_rate`, not the empty `perpetual_details.funding_rate` the
original probe checked). Amendment 5 (tradeability) and the funding-accrual question are both
resolved. Derivatives eligibility on this operator's CDE account is **resolved as of
2026-08-14** — approved for derivatives trading. It was always an account-status item, not a
research blocker, and clearing it does not itself authorize execution, which still requires this
document's own frozen specification and board transition.

## 3. Frozen specification — DRAFT, drafted 2026-08-13

**Not frozen.** Per this section's own placeholder text and Amendment 3, freezing requires a
review pass no earlier than one day after this draft. Nothing below is authoritative until that
pass and an explicit freeze commit.

Scope: carry capture only, per the clarification appended to Section 1. Universe, decision rule,
and output schema below; multiplicity and holdout structure follow Amendments 1-2.

### 3a. Open design fork — construction of the second leg

Every candidate position is delta-neutral: long the underlying, short the perpetual-style
contract (or the reverse, whichever side collects the currently-signed funding). The open
question is what the *first* leg is:

- **perp-vs-dated, both on CDE.** Satisfies Amendment 5 by construction — identical venue for
  both legs, no custody or cross-venue assumption. Available only where a same-root dated
  contract also trades liquidly on CDE; the feasibility finding confirmed this for 5 majors
  (BTC, ETH, XRP, SOL, DOGE) from a partial check, not the full 19.
  Amendment 5. Not yet checked systematically across all 19 names.
- **perp-vs-spot, spot leg off-CDE** (Coinbase's regular exchange). Covers the full 19-name
  cross-section but rests on an unvalidated assumption: that Coinbase spot custody and CDE
  futures margining compose into a coherent basis trade without material cross-venue friction.
  Same company, different venue — Amendment 5 is not satisfied by construction the way it is
  for the CDE-native pair.

`scripts/probe_cde_matched_pairs.py` (run 2026-08-13, `artifacts/campaign53_source_probe/
cde_matched_pairs_findings.json`): **10 of 19** liquid perpetual-style names have a tradeable
same-root dated contract on CDE — BTC, ETH, XRP, SOL, HYPE, XLM, LINK, DOGE, ADA, DOT.

**Resolved: perp-vs-dated on these 10 is the primary universe.** It satisfies Amendment 5 by
construction for the whole cross-section, needs no custody or cross-venue assumption, and is a
real improvement on the 5-name partial estimate the feasibility finding recorded. Still worth
noting as a genuine limitation: 10 is roughly half the liquid perpetual-style set, and the
missing half is not random — see below.

**Resolved 2026-08-13.** `probe_cde_product_detail.py` against the four odd names (`TEK-19DEC30
-CDE`, `CHN-19DEC30-CDE`, `AIP-19DEC30-CDE`, `DEF-19DEC30-CDE`) confirms they are equity-index
perpetuals, not crypto: `display_name` "Tech100 Perpetual" / "China Perpetual" / "AI Perpetual" /
"Defense Perpetual", `future_product_details.non_crypto = True` on all four,
`futures_asset_type = 'FUTURES_ASSET_TYPE_STOCKS'`, `trading_hours_type =
'TRADING_HOURS_TYPE_EQUITY_INDEX'`, and `twenty_four_by_seven = False` (every crypto contract
checked so far runs 24/7; these don't). Coinbase's product schema simply reuses the same
"perpetual-style futures on CDE" shape for equity-index products. Campaign #53's frozen Charter
(§1) scopes this family to crypto perpetuals only — these four were never in scope, independent
of matched-pair status, and are excluded on category grounds.

**Final resolved universe: 15 crypto names in the liquid perpetual-style set (19 minus these 4
equity-index products), of which 10 have a matched CDE dated contract** (BTC, ETH, XRP, SOL,
HYPE, XLM, LINK, DOGE, ADA, DOT) and are the primary universe under perp-vs-dated. The remaining
5 (PAXG, ZEC, NEAR, ENA, ONDO — PAXG a gold-backed token rather than a "pure" crypto-native
asset, noted without excluding it) have no CDE dated match and are a documented future extension
via perp-vs-spot, not part of this specification at freeze.

### 3a-i. Adversarial review, 2026-08-14 — the pivot to perp-vs-dated is not a free resolution

The paragraphs above frame perp-vs-dated as strictly superior to perp-vs-spot: satisfies
Amendment 5 by construction, no custody assumption, wider coverage than the earlier 5-name
estimate. That framing is incomplete, found on review, not before.

**This is not a pure funding-capture trade.** The frozen Charter's economic mechanism (§1)
describes funding as a payment that "pins the perp to spot" — a perp-vs-spot claim. Perp-vs-dated
is a hybrid: funding accrual on the perpetual-style leg, plus calendar-spread convergence as the
dated leg approaches its own expiry. These are different return sources with different behavior,
and the specification's target formula (§3c: "funding collected minus transaction costs minus
basis convergence/divergence") does account for the convergence term as a cost, which is
correct — but §3b's Amendment 4 argument ("funding is marked fresh each interval, so decision lag
doesn't invalidate it") is only true for the funding component. Calendar-spread convergence is a
genuinely decaying, time-bound quantity, and §3b did not say so.

**Contract roll is entirely unaddressed.** Several of the matched dated contracts carry an
`28AUG26` expiry — roughly two weeks out when this was first written, 2026-08-14. (Update,
2026-08-18: four real days have since passed; `28AUG26` is now roughly 10 days out. Noted here
rather than silently changing the original figure, consistent with this document's own
correct-in-place-don't-rewrite convention. The gap itself is closed — see §3a-ii below.) A live
position needs a defined roll policy (when, to which successor contract, at what cost) that did
not exist anywhere in this specification at the time. This is not a reason to abandon the design;
it was a real gap that needed its own subsection before Section 3 freezes, not an implicit
assumption.

**Resolved 2026-08-14, and both confirmed the concern rather than dismissing it.**
`scripts/probe_cde_history_depth.py`, run against real CDE endpoints: zero candles for either
BIP-20DEC30-CDE or ETP-20DEC30-CDE in a window 2.5 years before `new_at` — consistent with
`new_at` marking genuine product inception, not some unrelated schema field. Separately, all four
plausible historical-funding-endpoint patterns returned HTTP 404. Neither check alone is fully
conclusive (the candle check used one window, not a precise boundary search; the endpoint check
tried guessed patterns, not documentation-confirmed ones — this environment cannot reach
Coinbase's docs either, confirmed directly this session). Together they're decisive on the
question that actually matters: **even in the best case where an undiscovered funding-history
endpoint exists, CDE's crypto perpetual-style contracts are themselves only ~13 months old, which
caps how much history could ever exist regardless of endpoint availability.** This is not a
data-access problem with a workaround. It is the real age of the product.

**This breaks the frozen Charter's multi-year assumption and the specification needs to be
redesigned around it, not frozen as drafted.** Amendment 1 names its own remedies for exactly
this situation ("more data, broader cross-section, fewer gates, or abandonment") — "more data" is
foreclosed here (the instrument cannot be older than it is), leaving three live options, each a
real design decision rather than something to resolve unilaterally in this document:

1. **Broader cross-section** — relax the >$1M/day liquidity threshold to widen the universe
   beyond 10-15 names, trading statistical power gained from breadth against the execution and
   data-quality problems thinner names bring.
2. **Fewer gates** — simplify §3d's discovery/confirmation structure so less power is needed to
   clear it, at the cost of a less rigorous design.
3. **Split source and confirmation venue** — the frozen Charter's original "why the historical
   record can test it" section cites multi-venue funding history back to ~2019-2020 (Deribit
   among them, per the earlier feasibility work), before the pivot to CDE-only. Amendment 5
   already anticipates this shape: research source and execution venue may differ if the charter
   states why the premium should transfer and the specification includes a cross-venue basis
   check. A design that runs FDR discovery on Deribit's longer history, then confirms only on
   CDE's ~13-month native data for the instruments actually tradeable, maps directly onto
   Amendment 2's discovery/confirmation split and does not require abandoning the cross-sectional
   design.

**Decided 2026-08-14: option 3.** Discovery runs on Deribit's multi-year funding history;
confirmation runs only on CDE's native ~13-month data for the instruments actually traded.
Reasoning recorded here, not just the choice: options 1 and 2 were rejected because neither adds
real information — broadening the universe imports instruments likely even newer than BTC/ETH
PERP without lengthening the calendar, and fewer gates would lower the bar to fit the data rather
than strengthen the case. Option 3 is the only one that manufactures more of the actually-missing
ingredient (time) without weakening rigor anywhere, and it uses a mechanism Amendment 5 already
provides for exactly this shape of problem rather than inventing an exception.

**Resolved 2026-08-14 — Deribit covers 2 of 10, not the full universe.**
`scripts/probe_deribit_universe_coverage.py`: Deribit lists perpetual futures only for BTC and
ETH. The other eight (XRP, SOL, HYPE, XLM, LINK, DOGE, ADA, DOT) returned clean HTTP 200 empty
results — confirmed genuine absence, not a query failure, by direct inspection of one result
(SOL) before accepting the pattern across all eight. Option 3 as decided therefore rescues only
BTC and ETH with real rigor; it does nothing for the other eight, which is a second decision, not
a footnote to the first.

**Decided 2026-08-14 — option C for the eight: defer, don't exclude or downgrade.** BTC/ETH
proceed now under the Deribit-discovery / CDE-confirmation design decided above. The other eight
are neither excluded from Core v2 permanently nor folded in as a permanently-weaker exploratory
tier — both were live options and both were rejected. Exclusion reverses the entire rationale for
a cross-sectional design; permanent exploratory status bakes a compromise into the specification
forever for names that may not need one. Instead: CDE's own native history for these eight
continues accumulating from today regardless of any decision made here, at zero cost, and they
are revisited for inclusion once that history is long enough to support a genuine
development/validation/holdout split without needing a proxy venue at all. **How long "long
enough" is is not decided here** — it is itself a future judgment call, not a number to invent in
passing, and belongs to whichever session actually revisits this.

**This also resolves, by circumstance rather than correction, the frozen-Question mismatch noted
above.** The Question asks about "BTC and ETH" specifically. At the time that clarification was
appended, the resolved universe was a 10-name cross-section, and the mismatch was real. Now that
execution is deferred to BTC/ETH only, the Question's original wording is accurate again — not
because it was rewritten, but because the specification's actual scope came back around to match
it. Worth recording plainly rather than leaving two adjacent notes that look inconsistent to a
future reader.

### 3a-ii. Contract roll policy — resolved 2026-08-14

Closes the gap §3a-i named: dated legs expire, and a live position needs a defined policy for
what happens as expiry approaches. Four questions, each answered structurally rather than left
implicit.

**When to roll.** Not at expiry itself. Two things degrade as a dated contract approaches
settlement: liquidity migrates to the next-listed contract as open interest rolls over
market-wide, and the contract's own price mechanically converges toward spot, which is the
return this design exists to capture in the first place — rolling too late gives back captured
basis for no benefit, since there is nothing left to converge. The specification sets roll timing
as **N business days before expiry, N calibrated against CDE's observed liquidity-migration
curve for the specific contract, not assumed.** This mirrors how the FDR threshold in §3d is
left as "to be set at review" rather than invented here — N is a number that needs the operator's
own account access to CDE's order book depth over past roll events, which this environment cannot
reach.

**To which successor.** The next dated contract for the same underlying, if CDE has one listed
at roll time. This is not yet verified as a standing guarantee — the expiry distribution recorded
in the feasibility finding (65 contracts expiring in 2026, 6 in 2027, 28 in 2030) is consistent
with an active, maintained calendar, but "consistent with" is not "confirmed." **Before this
specification freezes, whoever executes the first roll needs to confirm directly that CDE lists
a successor contract for BTC and ETH before the current dated legs expire** — a live-account
check, not a research one, and cheap to do in the same session as opening the eligibility flow
already completed.

**At what cost.** Rolling means closing the expiring leg and opening the new one — a second
round-trip transaction cost on top of entry and exit, recurring on whatever cadence the dated
contracts actually expire at. §3c's target formula ("funding collected minus transaction costs
minus basis convergence/divergence") already nets transaction costs; this makes explicit that
"transaction costs" is not a one-time entry/exit figure but a recurring roll cost proportional to
how often the specific dated contract's calendar forces a roll. A shorter-dated contract rolled
more often costs more in aggregate fees for the same holding period than a longer-dated one —
worth factoring into which specific dated contract is chosen at each roll, not just rolling into
whichever one is next chronologically.

**How roll interacts with the signal.** Not a mechanical continuation of the old position. Each
roll is treated as **a fresh entry decision**: at roll time, the newly-formed pair (the same
perpetual-style leg against the new dated contract) is evaluated against §3c's candidates exactly
as any other prospective entry would be. If the candidate no longer clears the decision rule, the
position is not renewed — it exits to flat rather than being carried forward on the strength of a
signal that justified the original, now-expiring, contract pairing. This keeps every open position
justified by current candidate values, never by inertia.

### 3b. Horizon feasibility (Amendment 4) — carry does not fit the standard framing

Amendment 4's decay-horizon-vs-cadence test was built for directional signals that expire: a
prediction made now is only actionable if decided before the effect decays. Carry does not work
that way. A funding payment is marked and settled fresh every interval based on the
*then-current* rate, not a snapshot taken at entry. A ~1.5-1.7 bar decision lag (`CLAUDE.md`)
affects entry/exit price and the first payment observed, not the validity of every subsequent
payment the way it invalidated Jump Risk's signal.

The genuine horizon question for this family is different: **how autocorrelated is a given
instrument's funding regime** — is currently-elevated funding informative about funding over the
next N periods, enough to clear transaction costs on entry and exit? That is an empirical,
testable property of the frozen candidates, not a structural feasibility gate. It belongs in the
candidate formulas below, not as a pass/fail screen before specification, and this is noted here
so a future reader does not mistake its absence for an unconsidered gate.

**Completed 2026-08-14 — the calendar-spread component needs a different argument entirely, not
the funding argument stretched to cover it.** §3a-i named this gap directly: the above holds only
for the funding leg. Calendar-spread convergence is not a signal that decays and goes stale the
way a directional prediction does — it is closer to the opposite. A dated future's price is
**mechanically required** to converge to spot by its contract's own expiry; this is a structural
certainty of the instrument, not a statistical pattern that might or might not persist. Amendment
4 was written to catch effects that expire before a decision can be acted on. A guaranteed
convergence does not expire — if anything, decision lag matters less here than for funding,
since the eventual outcome (dated price → spot at expiry) does not depend on when within the
holding period the position was entered.

**What actually needs treating carefully is not decay, but mark-to-market risk before
convergence.** The spread can move against the position between entry and expiry even though its
terminal value is constrained — a real risk, just a different one than Amendment 4 addresses.
This means the calendar-spread candidate is not the same *kind* of candidate as the funding-level
and funding-persistence candidates in §3c, which are genuinely discovered, statistical
relationships subject to Amendment 2's FDR treatment. Basis at entry is closer to a structural,
cash-and-carry-style position: its expected value is grounded in contract mechanics, not
discovered by ranking candidates against history. **§3c's basis candidate should be evaluated
and reported separately from the funding candidates, not pooled into the same FDR family** — the
two need different decision logic (funding: does this historically predict forward returns;
basis: does the current spread, net of transaction and roll costs from §3a-ii, exceed the minimum
mark-to-market risk this operator is willing to carry to expiry) and conflating them would either
overstate the funding candidates' power (borrowing basis's structural certainty) or understate
basis's legitimacy (subjecting a mechanically-grounded position to a statistical-discovery
standard it doesn't need).

### 3c. Candidates

**Universe for this specification: BTC and ETH only**, per the 2026-08-14 deferral decision
above. Not the full 10-name set — the other eight are deferred, not part of this execution scope.

**Statistical family — subject to §3d's FDR/holdout treatment:**

- **Funding level** — trailing mean funding rate over windows {24h, 72h, 168h} per instrument.
- **Funding persistence** — fraction of periods in the trailing window with same-signed funding
  (autocorrelation proxy, directly targeting the §3b question).
- **Open interest change** — trailing percentage change, as a crowding proxy.

**Structural family — evaluated separately, per §3b's completed reasoning, not pooled with the
statistical family:**

- **Basis** — (perp price − matched leg price) / matched leg price, level and trailing change.
  Entry decision rule: current spread, net of transaction and roll costs (§3a-ii), must exceed
  the minimum mark-to-market risk this operator sets as tolerable to carry to the dated leg's
  expiry. No discovery-stage ranking, no FDR correction — the candidate's validity rests on
  contract mechanics, not on clearing a multiplicity-adjusted statistical bar.

Targets, statistical family only: forward net carry P&L (funding collected minus transaction
costs) at holding horizons {24h, 72h, 168h}. The basis/structural family's target is the
convergence P&L itself, realized at roll or expiry per §3a-ii, not a forward-return prediction.
"Cross-sectionally ranked" now means ranked across two instruments (BTC, ETH) at each rebalance,
not the ten originally scoped — worth being explicit that this is a materially narrower
cross-section than the design that motivated moving away from a single-asset approach in the
first place, accepted here as the honest cost of option C rather than glossed over.

### 3d. Decision rule and multiplicity (Amendment 2)

Applies to the statistical family only (§3c) — funding level, funding persistence, open interest
change. Discovery: rank candidates cross-sectionally at each rebalance by expected net carry; FDR
control (Benjamini-Hochberg, q to be set at review) across the full candidate × horizon family
rather than familywise correction, per Amendment 2's preference for broad families under FDR.
Confirmation: top-k shortlist from discovery, strict pre-registered decision rule and sign check
against the untouched terminal holdout.

The structural family (basis) does not enter this pipeline — per §3b, subjecting a
mechanically-grounded convergence trade to a statistical-discovery standard would misrepresent
what kind of claim it is. Its own decision rule is stated in full in §3c; nothing here overrides
it.

### 3e. Output schema

Per rebalance, per instrument: candidate values, entered/not, realized net carry, realized
basis P&L, transaction costs, holding period. Aggregated to portfolio-level NAV under the same
canonical conventions used elsewhere (LF-only artifacts, SHA-256 digests, two-pass replay
identity).

## 4. Power — PLAN ONLY, not executable yet

Amendment 1 requires a simulation-based estimate before any execution GO. That simulation needs
realistic candidate distributions, which need acquired historical funding/basis data — not yet
authorized (Section 2). This section states the approach; it does not produce a power number.
**Applies to the statistical family only** (§3c: funding level, funding persistence, open
interest change) — §3b and §3c both establish that the structural/basis family is not a
discovered statistical claim, so Amendment 1's power framing does not apply to it the same way;
its evidentiary standard is the mechanical convergence argument in §3b plus the cost threshold
in §3c, not a power simulation.

1. **Effect-size grid.** Realistic funding-carry Sharpe/IC has genuine academic and industry
   precedent distinct from the generic 0.02-0.05 IC range cited for price-predictive signals
   (Amendment 1's reference point) — carry premia are typically more persistent but also more
   competed-away at scale. The grid used here must be justified from comparable published/
   observed carry strategies, not asserted, at review time.
2. **Simulation.** Bootstrap or block-bootstrap the acquired historical funding series across BTC
   and ETH (§3c — the deferred eight are out of scope for this specification), discovering on
   Deribit's multi-year history and confirming on CDE's native ~13-month window, injecting a
   candidate effect at each grid size and measuring the fraction of resamples that clear every
   frozen gate in §3d.
3. **Threshold.** Standard: below 50% power at the central plausible effect size, the campaign
   does not proceed as specified. The usual remedies (broader universe, fewer gates, longer
   sample) were considered directly in §3a-i for this campaign specifically and rejected or
   deferred with reasoning recorded there — a future low-power result should not casually
   reopen options already decided against, without at least engaging with why they were rejected.

Blocked on: data acquisition authorization, itself blocked on this specification's freeze. The
history-depth and universe-scope questions that previously blocked this section are resolved —
BTC/ETH only, two-venue design, decided 2026-08-14.

## 5. Execution evidence

*Pending.*

## 6. Result

*Pending.*

## 7. Closure

*Pending.*
