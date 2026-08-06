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

## 3. Frozen specification

*Pending. Per Amendment 3, this section is appended and frozen by a later commit, no earlier
than one day after its first draft.*

## 4. Power

*Pending. Required before any execution GO, per Amendment 1.*

## 5. Execution evidence

*Pending.*

## 6. Result

*Pending.*

## 7. Closure

*Pending.*
