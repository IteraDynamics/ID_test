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
resolved. Derivatives eligibility on this operator's CDE account remains outstanding — an
account-status item, not a research blocker.

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

This closes the last open item ahead of Section 3's one-day-minimum review gate.

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

### 3c. Candidates

- **Funding level** — trailing mean funding rate over windows {24h, 72h, 168h} per instrument.
- **Funding persistence** — fraction of periods in the trailing window with same-signed funding
  (autocorrelation proxy, directly targeting the §3b question).
- **Basis** — (perp price − matched leg price) / matched leg price, level and trailing change.
- **Open interest change** — trailing percentage change, as a crowding proxy.

Targets: forward net carry P&L (funding collected minus transaction costs minus basis
convergence/divergence) at holding horizons {24h, 72h, 168h}, cross-sectionally ranked across
the resolved universe at each rebalance.

### 3d. Decision rule and multiplicity (Amendment 2)

Discovery: rank candidates cross-sectionally at each rebalance by expected net carry; FDR
control (Benjamini-Hochberg, q to be set at review) across the full candidate × horizon family
rather than familywise correction, per Amendment 2's preference for broad families under FDR.
Confirmation: top-k shortlist from discovery, strict pre-registered decision rule and sign check
against the untouched terminal holdout.

### 3e. Output schema

Per rebalance, per instrument: candidate values, entered/not, realized net carry, realized
basis P&L, transaction costs, holding period. Aggregated to portfolio-level NAV under the same
canonical conventions used elsewhere (LF-only artifacts, SHA-256 digests, two-pass replay
identity).

## 4. Power — PLAN ONLY, not executable yet

Amendment 1 requires a simulation-based estimate before any execution GO. That simulation needs
realistic candidate distributions, which need acquired historical funding/basis data — not yet
authorized (Section 2). This section states the approach; it does not produce a power number.

1. **Effect-size grid.** Realistic funding-carry Sharpe/IC has genuine academic and industry
   precedent distinct from the generic 0.02-0.05 IC range cited for price-predictive signals
   (Amendment 1's reference point) — carry premia are typically more persistent but also more
   competed-away at scale. The grid used here must be justified from comparable published/
   observed carry strategies, not asserted, at review time.
2. **Simulation.** Bootstrap or block-bootstrap the acquired historical funding/basis series
   across the resolved universe, inject a candidate effect at each grid size, and measure the
   fraction of resamples that clear every frozen gate in §3d (FDR at discovery, strict sign and
   decision rule at confirmation).
3. **Threshold.** Standard: below 50% power at the central plausible effect size, the campaign
   does not proceed as specified — the fix is redesign (broader universe, fewer gates, longer
   sample), not execution.

Blocked on: data acquisition authorization, itself blocked on this specification's freeze
(earliest 2026-08-14 per this section's own pacing rule). Universe is resolved (N=10 primary).

## 5. Execution evidence

*Pending.*

## 6. Result

*Pending.*

## 7. Closure

*Pending.*
