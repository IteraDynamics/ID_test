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
