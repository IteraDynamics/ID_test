# Campaign #53 — Source Feasibility Finding (2026-08-11)

## Status

**FEASIBILITY EVIDENCE — no campaign authorized, no data acquired, no specification frozen.**

Evidence: `artifacts/campaign53_source_probe/source_probe_findings.json`, produced by
`scripts/probe_funding_data_sources.py` (read-only).

## 1. Venue reachability

Reachability from this operator's location is itself a binding constraint, and was measured
rather than assumed.

| Venue | HTTP | Reachable | Note |
|---|---:|---|---|
| Binance | 451 | **No** | Jurisdictional block |
| Bybit | 403 | **No** | Jurisdictional block |
| OKX | 200 | Yes | Public funding history capped at ~92 days |
| Deribit | 200 | Yes | Deepest reachable history |
| Hyperliquid | 200 | Yes | Newer venue |
| dYdX | 200 | Yes | BTC paged; ETH returned a short series |
| Coinbase INTX | 200 | Yes (data) | Only ~100 rows returned; trading access unverified |

Binance holds the deepest and most liquid perpetual funding history in the market and is
**not available to this operator**. Campaign #53 must be designed around what is reachable.

## 2. History depth

| Venue | Asset | Rows | Earliest reached | Exhausted |
|---|---|---:|---|---|
| Deribit | BTC / ETH | 45,324 | 2021-06-10 | No — walk limit, not venue limit |
| Hyperliquid | BTC / ETH | 6,066 | 2025-12-01 | No |
| dYdX | BTC | 6,040 | 2025-12-03 | No |
| OKX | BTC / ETH | 276 | 2026-05-11 | **Yes — genuine venue cap** |
| Coinbase INTX | BTC / ETH | 100 | 2026-08-07 | Yes (endpoint returns a fixed window) |

**Deribit is the only reachable venue with research-grade depth**: over five years of hourly
observations, and the walk had not exhausted it. OKX, the first venue that responded, is a
live-data source rather than a research source — a 92-day window cannot support a
development / validation / untouched-holdout split.

## 3. Cross-venue consistency — the most important finding

Annualised mean funding, BTC, computed on each venue's declared rate period:

| Venue | Annualised |
|---|---:|
| Coinbase INTX | 5.37% |
| Deribit | 4.69% |
| Hyperliquid | 4.39% |
| OKX | 3.63% |
| dYdX | -4.23% |

Four of five independent venues cluster between 3.6% and 5.4%. That agreement is meaningful in
two ways:

1. **The premium is not a venue artifact.** Independent order books, independent funding
   mechanisms, and independent user bases price the same premium at a similar level. This is
   evidence the effect is structural rather than idiosyncratic.
2. **It materially reduces the Amendment 5 cross-venue basis concern.** Research conducted on
   Deribit history and executed elsewhere carries basis risk, but the observed dispersion is
   modest for the venues that matter.

dYdX diverges sharply and negatively. Its funding mechanism differs and its sample here is
shorter. It should not be pooled with the others without a separate justification.

These figures are sample means over unequal windows and are descriptive only. They are not a
return estimate.

## 4. Economic materiality — assessed before chartering

A delta-neutral carry harvest (long spot, short perpetual) collects funding while it is
positive. Taking Deribit's 4.69% as a gross reference:

| Allocation | Net at 60% capture | Net at 40% capture |
|---:|---:|---:|
| $10,000 | $282/yr | $188/yr |
| $20,000 | $564/yr | $376/yr |
| $30,000 | $846/yr | $564/yr |
| $50,000 | $1,410/yr | $940/yr |

Capture is well below gross because the position pays fees on two legs, funding is not always
positive, and the trade consumes capital on both sides.

**This is the same order of magnitude as the Jump Risk edge that was just retired.** Funding
carry is a low-return, low-risk, uncorrelated sleeve — a cash alternative, not an alpha engine.
Its portfolio value at this capital scale lies in diversification and Sharpe contribution, not
in dollars.

Recording this before chartering is deliberate. The Jump Risk episode consumed substantial
effort on an edge whose materiality was never assessed against this operator's actual capital.

## 5. Tradeability — RESOLVED (2026-08-11)

Operator account inspection confirms **perpetual futures are listed and marked tradable** on
**Coinbase Derivatives Exchange (CDE)**, a CFTC-regulated US venue, alongside a dated-futures
series.

Perpetual products observed under the "Tradable" filter:

| Product | Contract size | Last | 24h volume |
|---|---:|---:|---:|
| BTC PERP | 0.01 | $63,735 | $239.58M |
| ETH PERP | 0.1 | $1,873.0 | $47.12M |
| TECH PERP | 1 | $3,979.6 | $21.81M |
| PAXG PERP | 1 | $4,385.8 | $19.38M |
| XRP PERP | 500 | $1.0022 | $19.38M |
| SOL PERP | 5 | $75.24 | $12.18M |
| ZCASH PERP | 1 | $474.00 | $7.44M |
| NEAR PERP | 500 | $1.5487 | $5.57M |
| HYPE PERP | 10 | $54.31 | $5.15M |
| AI PERP | 1 | $2,969.3 | $3.85M |
| XLM PERP | 5K | $0.16021 | — |

**Gating step:** the account has not completed derivatives onboarding. Coinbase presents an
eligibility questionnaire ("Unlock derivatives trading… Coinbase Financial Markets"). Charter
authorization is contingent on that eligibility being granted, which is not guaranteed and may
depend on jurisdiction and suitability.

Contract granularity is workable at this capital scale: BTC PERP is roughly $637 notional per
contract, ETH PERP roughly $187.

### 5a. Critical distinction — CDE is not INTX

The probe measured **Coinbase International Exchange (INTX)** funding at 5.37% annualised. The
operator would trade **Coinbase Derivatives Exchange (CDE)**. These are different venues with
different participants, different access rules, and potentially different funding levels.

**No CDE funding history has been obtained.** Deribit remains the only research-grade source,
and the Amendment 5 cross-venue basis requirement is therefore *not* satisfied by the INTX
figure. Before the specification freezes, the charter must establish either CDE funding history
directly, or evidence that CDE funding tracks the research venue closely enough to rely on.

### 5b. Observation — dated-futures basis

A snapshot showed BTC PERP at $63,735 against the BTC 28-AUG-26 dated future at $64,000: a
0.416% spread over roughly 17 days, or approximately 8.9% annualised. This is a single
unverified observation from a screenshot, not a measurement, and the two prices may not be
synchronous.

If it holds up, the calendar basis may be a larger and more accessible premium than perpetual
funding, harvestable with a defined expiry and no funding-rate uncertainty. It is recorded as a
candidate for separate investigation, not as a finding.

## 6. Campaign design implication — go cross-sectional

The original charter contemplated a time-series carry study on BTC and ETH. The observed
universe contains **eleven or more perpetual products**, which changes the appropriate design.

A cross-sectional funding study — ranking the available perp universe by funding and trading
the spread between extremes — is materially better than a two-asset time-series study on three
counts:

1. **Power.** Funding is heavily autocorrelated, so a year of BTC funding contains far fewer
   independent observations than its row count suggests. A cross-section of eleven instruments
   multiplies independent observations without requiring more history — directly addressing the
   Amendment 1 constraint that ended Campaigns #50–#52.
2. **Economics.** More instruments means more simultaneous opportunities and less dependence on
   any single funding regime.
3. **Mechanism.** Cross-sectional dispersion in funding is a cleaner crowding measure than any
   single asset's level, since it controls for market-wide risk appetite.

Liquidity is the constraint: BTC and ETH PERP carry meaningful volume, while the tail products
trade in the single-digit millions. A cross-sectional design must include a pre-registered
liquidity floor and a capacity assumption sized to this operator's capital.

## 7. Superseded — original open blocker

Per Amendment 5, Campaign #53 cannot be chartered until this is answered:

> **Which perpetual or futures instruments can this operator actually trade, on which venue,
> given jurisdiction and account status?**

Coinbase is the operator's execution venue. Coinbase lists perpetuals on Coinbase International
Exchange, whose *market data* is publicly reachable (confirmed above) but whose *trading access*
is jurisdictionally restricted. Reachable data does not imply a tradeable instrument.

This question is unresolved and blocks the charter.

## 6. Contingent paths

**If perpetuals are tradeable** — Campaign #53 proceeds as a carry study. Deribit provides the
research history; the charter must name the execution venue and include a cross-venue basis
check.

**If only dated futures are tradeable** — funding is not directly harvestable. The related
calendar-basis premium may be, but it is a different research subject requiring its own
evidence.

**If spot only** — carry harvesting is unavailable, and Campaign #53 as currently chartered
must be withdrawn. The recommended pivot is to research funding and open interest as a
**crowding and positioning signal conditioning existing spot exposure**, rather than as a
carry trade. That reformulation:

- requires no perpetual access, satisfying Amendment 5 trivially;
- retains a multi-day decay horizon, satisfying Amendment 4;
- uses the same reachable Deribit history;
- adds information to Core v1's existing crypto sleeves rather than adding a sleeve;
- and is arguably the stronger economic story, since persistently extreme funding is a direct
  measure of leveraged crowding.

## Authorization boundary

Observation-only. No data acquired, no campaign authorized, no specification frozen, and no
runtime, strategy, portfolio, or production change.

---

## 8. CDE universe resolved — and a redirect (2026-08-11)

`scripts/inspect_cde_universe.py` against the saved findings resolves the venue confusion and
changes the recommended campaign.

### 8a. The tradable universe was mislabelled, not missing

Coinbase Derivatives Exchange lists US-regulated **perpetual-style futures as very-long-dated
contracts**: `BIP-20DEC30-CDE` (contract 0.01) is the app's "BTC PERP", `ETP-20DEC30-CDE`
(contract 0.1) is "ETH PERP". Contract sizes match the app exactly. The Advanced Trade API
classifies these as `EXPIRING`, which is why a `PERPETUAL` filter returned only Coinbase
*International* Exchange products — a venue this operator does not trade.

CDE composition (99 products):

| Cohort | Products | Above $1M/day |
|---|---:|---:|
| Perpetual-style (2029+ expiry) | 28 | **20** |
| Dated futures | 71 | **10** |

Twenty liquid perpetual-style instruments is a genuine cross-section — sufficient breadth for a
properly powered cross-sectional design, which is precisely what Campaigns #50–#52 lacked.

### 8b. Funding is not published for CDE — the Amendment 5 gap stands

**Zero of 99 CDE products expose a `funding_rate` field.** A funding-carry campaign would have
to research Deribit's premium and collect CDE's, with no evidence the two match. Amendment 5 is
not satisfied and a funding campaign cannot be chartered on this basis.

### 8c. Matched pairs — a cleaner hypothesis

Five underlyings list **both** a perpetual-style and a dated contract, both liquid, both on CDE,
tradable in one account with no cross-venue exposure:

| Underlying | Perpetual-style | Dated | Spread | Days | Annualised |
|---|---:|---:|---:|---:|---:|
| BTC | 63,575.00 | 63,780.00 | 0.322% | 17 | 6.9% |
| ETH | 1,859.50 | 1,865.00 | 0.296% | 17 | 6.4% |
| XRP | 0.9999 | 1.0048 | 0.490% | 17 | 10.5% |
| SOL | 74.84 | 74.86 | 0.027% | 17 | 0.6% |
| DOGE | 0.0702 | 0.0709 | 0.997% | 17 | 21.4% |

The implied financing rate ranges from roughly 0.6% to 21% annualised across five underlyings
at the same instant. **That dispersion is the cross-sectional signal**, and unlike funding it is
computed directly from two prices this operator can observe and trade.

**These figures are a single non-synchronous snapshot and are not a measurement.** They
establish that the spread exists and disperses, nothing more.

### 8d. Recommended redirect

Campaign #53 should be re-chartered from **funding carry** to **cross-sectional calendar basis
on CDE**:

| | Funding carry | Calendar basis |
|---|---|---|
| Research data | Deribit (proxy venue) | CDE prices — same venue as execution |
| Amendment 5 | **Unsatisfied** | Satisfied by construction |
| Cross-section | Requires INTX (untradable) | 5+ matched pairs on CDE |
| Observability | Funding not published for CDE | Both legs directly quoted |

**Honest caveat, recorded before any design work.** A long-perp-style / short-dated position
still accrues funding on the perpetual-style leg, and that funding is a component of the trade's
P&L. Its absence from the public endpoint is therefore a real gap for basis research too, not
only for a funding campaign. Three possible resolutions, to be settled in the charter:

1. locate a CDE funding source (account statements, a different endpoint, or the FCM feed);
2. restrict the study to **dated-versus-dated** spreads, which carry no funding at all — the
   expiry distribution shows 65 contracts in 2026, 6 in 2027 and 28 in 2030, so some
   same-underlying dated pairs exist, though far fewer than the perpetual-style pairs;
3. treat funding as an unmeasured cost and require the basis premium to exceed a
   conservatively assumed funding drag, pre-registered before results.

Option 2 is the cleanest and option 3 the most honest; neither is chosen here.

### 8e. Status

Campaign #53 remains **unchartered**. Its subject has provisionally moved from funding carry to
cross-sectional calendar basis, pending resolution of the funding-accrual question above and
completion of derivatives eligibility. No specification is frozen and no data has been acquired.

---

## 9. Funding-accrual gap resolved — the probe read the wrong field (2026-08-12)

Section 8b's conclusion — "zero of 99 CDE products expose a `funding_rate` field" — is
corrected. **The data was never missing; the probe was reading the wrong path.**

`probe_coinbase_derivatives_universe.py` reads `future_product_details.perpetual_details
.funding_rate`, which is genuinely empty for every CDE product — that field appears to be
vestigial, populated only for Coinbase International's true `PERPETUAL`-typed products, not
CDE's `EXPIRING`-typed perpetual-style futures. `future_product_details.funding_rate` — a
sibling field one level up, alongside `contract_expiry`, `settlement_price`, and `index_price`
— is populated. `scripts/probe_cde_product_detail.py` confirmed it directly against the
single-product detail endpoint for both liquid perpetual-style majors:

| Product | funding_rate | funding_interval | funding_time | index_price |
|---|---:|---:|---|---:|
| BIP-20DEC30-CDE (BTC PERP) | 0.000011 | 3600s | 2026-08-12T20:00:00Z | 63,437.911245 |
| ETP-20DEC30-CDE (ETH PERP) | 0.000008 | 3600s | 2026-08-12T20:00:00Z | 1,881.933167 |

Both current, both timestamped, both on an **hourly** funding interval — notably different
cadence from Deribit's 8-hour convention, worth carrying into any specification that compares
the two.

### Full cross-section confirmed (2026-08-12)

`scripts/probe_cde_funding_coverage.py`, run fresh against the live universe rather than a
saved file: **19 of 19** liquid (>$1M/day) CDE perpetual-style products publish
`future_product_details.funding_rate`. Coverage is complete, not partial — every instrument a
cross-sectional design would draw from carries the field, from BTC ($231M/day) down to the
smallest liquid name (~$1.2M/day). The cross-section spans majors and a broad set of smaller
names (index prices from ~$0.07 to ~$63,500), which is real breadth for Amendment 1 power, not
a handful of large-cap coincidences.

### Consequence for campaign design

The Amendment 5 funding-accrual gap that motivated the calendar-basis redirect (§8d) **does not
exist**. CDE publishes native, same-venue, per-instrument funding directly, for the full liquid
cross-section. None of the three contingency options recorded in §8d are needed.

**Decision: Campaign #53 reverts to funding carry as its primary subject**, superseding the
§8d calendar-basis redirect. Funding carry is the cleaner design now that its blocker is gone —
native data, same venue as execution, no proxy, no assumed cost — and it was the original
economic hypothesis before the redirect existed only to route around a gap that turned out to
be a probe reading the wrong field. Calendar basis remains a valid, fully-scoped fallback
subject if funding carry fails a later gate, but is no longer the primary design.

Housekeeping for whoever builds the specification: several liquid contract codes (e.g. `TEK`,
`PAU`, `XPP`, `NER`, `HYP`) are not self-evident tickers and need mapping to their underlying
asset before use.

### Status

Campaign #53 remains **unchartered**. Funding-accrual and tradeability are both resolved.
Derivatives eligibility remains the one outstanding account-status item, blocking execution but
not research/specification work. No specification is frozen and no data has been acquired.

**Update, 2026-08-14:** derivatives eligibility is resolved — the operator's account was
approved for derivatives trading. This feasibility record is kept as-is above (an evidentiary
log, not the living document); the campaign's actual current state, including this resolution,
is tracked in `docs/research/CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md`.
