# Campaign #53 — Perpetual Funding and Basis Carry

## 1. Charter

### Status

**PLANNING CHARTER. Section 3 and Section 4 (methodology) FROZEN 2026-08-20.** Universe
(BTC/ETH), venue design (Deribit discovery, CDE confirmation), roll policy, candidates, and
decision rule (FDR q=0.10, confirmation top-3) do not change further.

No Campaign #53 predictor, outcome, ranking, or economic result exists yet — freezing the
specification is not the same as having run it. Data acquisition is authorized by the board
transition recorded on `docs/ITERA_CAMPAIGN_BOARD.md`, alongside this freeze.

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

## 3. Frozen specification — FROZEN 2026-08-20 (drafted 2026-08-13)

Six real days and a genuine fresh-eyes review pass (2026-08-20, which closed the two remaining
decision-rule gaps in §3d — FDR q and confirmation k, both previously deferred to "review"
without a concrete value) separate this freeze from the original draft, satisfying Amendment 3's
pacing rule. Universe (BTC/ETH, two-venue Deribit-discovery/CDE-confirmation design), roll policy,
candidate families, and decision rule do not change further below this point.

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
with an active, maintained calendar, but "consistent with" is not "confirmed." **Before the first
roll is executed, whoever executes it needs to confirm directly that CDE lists a successor
contract for BTC and ETH before the current dated legs expire** — a live-account check, not a
research one, and cheap to do in the same session as opening the eligibility flow already
completed. This is an execution-time check, not a freeze condition: the specification below
freezes a *policy* ("roll into the next-listed same-root contract"), and a frozen policy does not
require its future precondition to already be confirmed true today — the same distinction this
document draws everywhere else between freezing a design and authorizing its execution.

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

### 3a-iii. CDE historical funding data — not obtainable for this account, confirmation stage redesigned (2026-08-21)

§3a-i's "Decided 2026-08-14: option 3" assumed CDE's own native ~13-month funding history would
be retrievable for confirmation. That assumption was never actually verified — the original
four-pattern endpoint probe 404'd on all guesses and was recorded as inconclusive, not resolved,
and the freeze on 2026-08-20 proceeded without re-checking it. This closes that gap with a real
answer instead of an assumption.

**The endpoint is real.** The operator found it directly in Coinbase's own developer
documentation (`docs.cdp.coinbase.com`, unreachable from this research environment, which is why
guessing never found it): `GET /rest/funding-rate` at `https://api.exchange.fairx.net` — a
different domain entirely from every prior probe, and CDE-specific (FairX was the CFTC-regulated
exchange Coinbase acquired to become CDE). Confirmed via direct testing: the symbol format
(`BIPZ30`/`ETPZ30`, standard futures month-code notation matching the confirmed `20DEC30`
expiry) is correct, and the endpoint requires authentication via the classic Coinbase
Exchange/Pro-era scheme (`CB-ACCESS-KEY`/`SIGN`/`TIMESTAMP`/`PASSPHRASE`, HMAC-SHA256) —
confirmed by the server's own error response, not inferred (`{"error":"missing request header:
CB-ACCESS-PASSPHRASE"}`).

**That credential type is not obtainable on this account.** Neither the Coinbase Developer
Platform (JWT-based keys, no passphrase field) nor Advanced Trade (key + secret only) issue it.
`exchange.coinbase.com` — the legacy portal that does issue key/secret/passphrase credentials —
gates access behind a business-account application; this operator is retail. Coinbase support,
escalated to a specialist team, confirmed directly: *"This falls outside of what our support team
can provision... this is a known platform-level gap between the two systems, not something
missing on your end."* Not a configuration error, not a missing step — a genuine platform gap for
retail accounts, confirmed by Coinbase's own support organization.

**Confirmation stage redesigned: live-forward accumulation, not backfill.** CDE's *current*
funding rate snapshot — the same `future_product_details.funding_rate` field confirmed accessible
in the original 2026-08-12 feasibility work, no special credential required — remains available.
The confirmation holdout will be built by logging that field going forward from whenever
acquisition begins, not backfilled from history. **No fixed window is assumed.** The "~13 months"
figure was never a computed requirement — it was however much history CDE's contracts happened to
have, not a power-derived minimum. The actual minimum confirmation sample needed comes from
Section 4's power analysis, which requires real accumulated data to calibrate against and has not
been run. This is expected to be materially shorter than 13 months for a persistent premium (per
§1's own economic-mechanism argument), but that is not yet known and is not asserted here.

**This does not block discovery.** Deribit's multi-year funding history is unaffected by any of
this and remains available immediately. Discovery proceeds now; confirmation data accumulates in
parallel starting whenever live logging begins, not as a gate in front of everything else.

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

**Rebalance frequency — resolved 2026-08-21, another gap the freeze review missed.** §3c never
actually stated how often positions rebalance; "at each rebalance" was left undefined. **Set to
daily (24h)** — matches the shortest of the three {24h, 72h, 168h} horizons, and keeps the
family's overlapping-window autocorrelation burden bounded rather than compounding it with
hourly rebalancing against multi-day horizons. Each candidate's own lookback window is paired
with the matching target horizon (24h window → 24h horizon, 72h → 72h, 168h → 168h) rather than
crossed against all three — the simpler, more defensible reading of "candidate × horizon family"
in §3d below, avoiding a 3x larger multiplicity family than what the FDR budget was actually
sized for. With only two instruments, statistical power here comes mostly from the time
dimension (daily rebalances across multiple years) rather than genuine cross-sectional breadth
— the same honest cost of option C already named above, worth restating precisely now that a
power simulation is being built around it.

**Window narrowing — corrected 2026-08-21, after the first real power-analysis run.** The
frozen `{24h, 72h, 168h}` window set above ran against real acquired Deribit data
(`scripts/run_campaign53_power_analysis.py`) with correctly-fixed block-bootstrap machinery
(see the 2026-08-21 `inject_ic` bug fix in the script's own history) and a new diagnostic
printing each hypothesis's real lag-1 autocorrelation alongside its null-reference width. Real
result: **average power at the central IC estimate (0.065) = 45.4%**, below Amendment 1's 50%
floor — an underpowered null under the frozen six-hypothesis (funding level × funding
persistence, three windows each) family actually tested. The diagnostic confirmed the fix
itself is correct (null width scales with measured autocorrelation exactly as expected —
BTC/ETH funding_level candidate/target lag-1 autocorrelation measured 0.71/0.71 at 24h,
0.92/0.92 at 72h, 0.98/0.98 at 168h, and the null widened in step: 0.018 → 0.027 → 0.034), but
it also showed the family average is dragged down by a structural, predictable-in-advance
mechanism, not genuine uncertainty about the effect: a 168h trailing/forward window resampled
at the daily rebalance cadence shares roughly 86% of its underlying data with the immediately
preceding day's window, collapsing effective independent sample size and power regardless of
the true effect size (`funding_level_168h` measured 15-25% power even out to IC=0.08;
`funding_level_72h` similarly weak at 14-43%). `funding_persistence_24h`, by contrast, is
well-powered on the same data (64-95% power across the plausible IC range) because its
candidate has much lower autocorrelation (0.29) than the level candidates.

This is a design correction made on the family's own sensitivity characteristics — window
overlap, autocorrelation, effective sample size — established before looking at any real
candidate-target correlation, not a selection made on which candidate happened to look
promising. It is therefore consistent with Amendment 1's power-analysis-before-execution
requirement rather than a violation of it. **The window set for the statistical family (§3c) is
corrected from `{24h, 72h, 168h}` to `{24h, 72h}`**, dropping the 168h horizon across every
signal in the statistical family (funding level, funding persistence, open interest change).
The full statistical family accordingly shrinks from 3 signals × 3 windows = 9 candidate-horizon
combinations to 3 signals × 2 windows = **6**. (The power analysis script itself currently
implements only 2 of the 3 signals — funding level and funding persistence; open interest is
not yet acquired, per the pending `scripts/probe_deribit_open_interest_history.py` result — so
its own family is a further, data-availability-driven subset of 2 signals × 2 windows = 4, the
same kind of deliberate, documented approximation already accepted for the CDE-confirmation
gap below.)

**Re-run 2026-08-24: PASS at 56.0% average power** — see §4's "Corrected family re-run" for the
full result and breakdown.

**`funding_level_24h` excluded 2026-08-24 — found by the first real discovery run, not by
inspection.** The operator authorized real predictor/outcome computation on the discovery half of
§3d (below); the first run of `scripts/run_campaign53_discovery.py` against real acquired Deribit
data put `funding_level_24h` at the top of the shortlist (r=0.7075). That result does not survive
scrutiny: funding_level's 24h candidate window, 24h target horizon, and the 24h daily rebalance
interval (set above) are all numerically identical. A candidate's trailing-mean window at day
t+1 is therefore EXACTLY the target's forward-sum window at day t — `target_t ≈ 24 ×
candidate_{t+1} − cost`, a near-deterministic linear identity, not an approximation. Pearson
correlation is invariant to positive linear rescaling, so `corr(candidate, target)` for this one
hypothesis collapses to `candidate`'s own lag-1 autocorrelation regardless of whether funding
level has any real predictive relationship to forward carry distinct from mere day-to-day
persistence — which the charter's §3b already assumes and cites, so this is not a new finding
about the world, it is a restatement of an existing assumption dressed up as a discovery.

Proven independent of the real data, not just observed on it: synthetic series (pure white
noise, and AR(1) processes at multiple persistence levels) were fed through the identical
candidate/target construction. For the 24h window, `corr(candidate, target)` matched
`candidate`'s own lag-1 autocorrelation to within 0.001–0.0006 at every tested sample size and
every tested autocorrelation level — including pure noise, where a genuine predictive
relationship is impossible by construction. The 72h window, tested as a control under the same
procedure, showed no such identity (differences of 0.68–0.85, i.e., the two quantities are
unrelated) — confirming the defect is specific to the 24h/24h/24h coincidence (window = horizon =
rebalance interval), not a general property of funding_level or of the 1:1 window/horizon
pairing convention. `funding_persistence` at 24h is unaffected for a different, also-verified
reason: its sign-matching transform is nonlinear, so the same algebraic collapse does not apply
(its null correlation shrinks toward zero with sample size, the way a real null should, rather
than pinning to a fixed nonzero value). Regression tests for both the defect and its scope (the
72h control) are in `tests/test_campaign53_power_analysis.py`.

**`("funding_level", 24)` is added to `EXCLUDED_HYPOTHESES`** in
`scripts/run_campaign53_power_analysis.py`, imported directly by the discovery script rather than
reimplemented. The statistical family (as currently implemented — funding level and funding
persistence, pending open interest change per §3c above) is now **three** candidate-horizon
hypotheses, not four: `funding_level_72h`, `funding_persistence_24h`, `funding_persistence_72h`.
Confirmation stays at top-2 (§3d below) rather than being re-derived to a new ratio against this
temporary, data-availability-limited subset — top-2 of 3 (67% selectivity) looks looser than the
originally-reasoned ~33%, but the subset itself is already an accepted approximation (2 of the
full family's 3 planned signal types are implemented; open interest is pending), and the *full*
frozen family once open interest is added would be five members (funding_level_72h,
funding_persistence at both windows, open_interest_change at both windows — open interest is
built from a different underlying series than the funding-based target, so it does not inherit
this exclusion), putting top-2 back near 40%, closer to the original ratio than the current
subset's 67%. Not worth inventing a new precise ratio against a denominator that is itself
temporary.

This does not reopen the discovery result computed before this correction — that result is
superseded, not archived as valid-with-caveats. Re-run required.

### 3d. Decision rule and multiplicity (Amendment 2)

Applies to the statistical family only (§3c) — funding level, funding persistence, open interest
change. Discovery: rank candidates cross-sectionally at each rebalance by expected net carry; FDR
control (Benjamini-Hochberg, **q = 0.10**) across the full candidate × horizon family rather than
familywise correction, per Amendment 2's preference for broad families under FDR. q = 0.10 rather
than the stricter 0.05 typically reserved for confirmation, consistent with Amendment 2's
two-stage design (permissive at discovery, strict at the untouched holdout) — this is a
methodology choice fixable now, unlike §3a-ii's roll-timing N or §3b's mark-to-market risk
tolerance, which genuinely need data this specification doesn't have yet. Confirmation: **top-3**
shortlist from discovery (the statistical family is 3 signals × 3 horizons = 9 candidate-horizon
combinations total; top-3 tests more than a single cherry-picked winner while still being a real
filter against a 9-member family), strict pre-registered decision rule and sign check against the
untouched terminal holdout.

The structural family (basis) does not enter this pipeline — per §3b, subjecting a
mechanically-grounded convergence trade to a statistical-discovery standard would misrepresent
what kind of claim it is. Its own decision rule is stated in full in §3c; nothing here overrides
it.

**Confirmation-k corrected 2026-08-21, alongside §3c's window narrowing.** Top-3 was sized
explicitly against the 9-member family ("top-3 tests more than a single cherry-picked winner
while still being a real filter against a 9-member family" — a stated ~33% selectivity ratio).
§3c's window correction shrinks the full statistical family from 9 to 6 candidate-horizon
combinations; leaving top-3 unchanged would silently loosen the filter to 50% selectivity
without that ever being a deliberate decision. **Confirmation is corrected from top-3 to
top-2** (2/6 ≈ 33%, preserving the originally-reasoned ratio rather than the raw count). FDR
q=0.10 at discovery is unaffected by this change and remains as frozen above.

### 3e. Output schema

Per rebalance, per instrument: candidate values, entered/not, realized net carry, realized
basis P&L, transaction costs, holding period. Aggregated to portfolio-level NAV under the same
canonical conventions used elsewhere (LF-only artifacts, SHA-256 digests, two-pass replay
identity).

## 4. Power — methodology FROZEN 2026-08-20, not executable yet

Amendment 1 requires a simulation-based estimate before any execution GO. That simulation needs
realistic candidate distributions, which need acquired historical funding/basis data — not yet
authorized (Section 2). This section states the approach; it does not produce a power number.
**Applies to the statistical family only** (§3c: funding level, funding persistence, open
interest change) — §3b and §3c both establish that the structural/basis family is not a
discovered statistical claim, so Amendment 1's power framing does not apply to it the same way;
its evidentiary standard is the mechanical convergence argument in §3b plus the cost threshold
in §3c, not a power simulation.

1. **Effect-size grid — set 2026-08-21, reasoned estimate, not literature-cited.** This research
   environment has no live internet access, so the grid below could not be built from actual
   published carry-strategy figures as this item originally called for. Set instead from general
   reasoning stated explicitly, not asserted as fact: IC = {0.02, 0.05, 0.08, 0.12}, with 0.05-0.08
   treated as the central plausible estimate. 0.02 anchors to Amendment 1's own generic
   price-signal reference point as a floor; 0.12 anchors to the upper end of what a
   less-competed, genuinely persistent premium might plausibly show in a two-instrument crypto
   sample, not a generic liquid-market factor. **This grid should be replaced with real citations
   before being treated as final** — flagged here rather than silently presented as sourced.
2. **Simulation.** Bootstrap or block-bootstrap the acquired historical funding series across BTC
   and ETH (§3c — the deferred eight are out of scope for this specification), discovering on
   Deribit's multi-year history and confirming on CDE's native ~13-month window, injecting a
   candidate effect at each grid size and measuring the fraction of resamples that clear every
   frozen gate in §3d.
   **Interim methodology note, 2026-08-21:** real CDE confirmation data does not exist yet
   (§3a-iii — live-forward accumulation, not backfilled). Until it does, the simulation
   approximates confirmation with a held-out chronological split of the same Deribit series
   rather than genuinely separate venues — a real limitation, not the frozen design, and stated
   as such in the simulation's own output rather than presented as equivalent to true CDE
   confirmation.
3. **Threshold.** Standard: below 50% power at the central plausible effect size, the campaign
   does not proceed as specified. The usual remedies (broader universe, fewer gates, longer
   sample) were considered directly in §3a-i for this campaign specifically and rejected or
   deferred with reasoning recorded there — a future low-power result should not casually
   reopen options already decided against, without at least engaging with why they were rejected.

**Real result and correction, 2026-08-21.** The simulation ran against real acquired Deribit
data (discovery-side, per §2's authorization) with a correctly-fixed `inject_ic` — average power
at the central IC = **45.4%, below the 50% threshold in item 3 above.** Per item 3's own
instruction, this result should not casually reopen options already rejected in §3a-i without
engaging why. It does not: §3a-i's "broader cross-section" and "fewer gates" remedies were
rejected for a different problem (CDE's categorically insufficient contract age, where no design
choice manufactures more calendar time except changing venue split) and specifically warned
against loosening the decision rule to opportunistically fit the data. §3c's window-narrowing
correction above is not that — it removes one candidate-horizon combination identified by a
mechanistic, effect-independent property (168h windows resampled daily share ~86% of their
underlying data with the prior day's window, collapsing effective sample size regardless of
whether a true effect exists) established from autocorrelation diagnostics, not from which
candidate happened to show a stronger correlation. §3d's confirmation-k correction (top-3 →
top-2) preserves rather than loosens the original ~33% selectivity ratio. Net effect on rigor:
neutral to slightly stricter, not weaker.

**Corrected family re-run, 2026-08-24 — PASS.** Average power at the central IC (0.065) =
**56.0%**, clearing the 50% floor. Per-hypothesis breakdown at IC=0.065 (interpolated):
`funding_persistence_24h` strong (~84%), `funding_persistence_72h` moderate (~62%),
`funding_level_24h` moderate (~45%), `funding_level_72h` weak (~34%) — uneven, carried
disproportionately by the two persistence candidates and especially the 24h one, consistent with
its markedly lower candidate autocorrelation (0.29 vs 0.71-0.92 for the others) giving it a
tighter, more sensitive null. The margin above the 50% floor is real but not wide (6 points),
and rests on an uncited effect-size grid (§4 item 1) and a confirmation stage still approximated
against a held-out Deribit split rather than real CDE data (§4 item 2) — both flagged, neither
resolved by this PASS. This result authorizes moving toward real discovery/confirmation
execution under Amendment 1; it is a campaign-board decision, not something this document
grants on its own (see `docs/ITERA_CAMPAIGN_BOARD.md`).

Blocked on: sufficient accumulated CDE confirmation data to calibrate the simulation against
(§3a-iii — live-forward accumulation, no fixed window, not backfillable). Discovery-side
acquisition (Deribit) is unblocked and can proceed now; this section's power number specifically
needs real accumulated CDE data, which does not yet exist. The history-depth and universe-scope
questions that previously blocked this section are resolved — BTC/ETH only, two-venue design,
decided 2026-08-14.

## 5. Execution evidence

*Pending.*

## 6. Result

*Pending.*

## 7. Closure

*Pending.*
