# Exploration Screen — Index-Options Dealer Gamma Pressure

**Status:** DATA INVENTORY / SCREEN NOT YET EXECUTED
**Date:** 2026-09-02
**Governance:** `docs/ITERA_EXPLORATION_SANDBOX.md`

## Screen card

- **Mechanism:** options dealers dynamically hedge inventory. Net short-gamma inventory should induce procyclical underlying hedge flow (buy into rises, sell into declines); net long-gamma inventory should induce countercyclical hedge flow. The proposed edge is compelled risk-management flow, not a generic price anomaly.
- **Survival argument:** dealers hedge because of option-book risk constraints, not because the hedge maximizes standalone alpha. The underlying flow can therefore persist despite being understood by sophisticated participants, although the observable proxy for aggregate dealer inventory may be noisy.
- **Instrument / venue:** SPY for the sandbox response variable; SPY is already tradeable by the operator. SPX/SPY option data are research inputs only at this stage.
- **Horizon sanity:** test next 1, 2, and 5 trading-day continuation/reversal and realized movement. These horizons comfortably exceed the currently measured ~0.5-0.6h runtime reaction cadence.
- **Falsification:** a causal dealer-position proxy fails to separate subsequent SPY continuation/reversal or realized movement from shuffled/random state labels; expected sign fails; result is dominated by one crisis/window; or causal historical positioning data cannot be sourced within the sandbox budget.
- **Budget:** one working session for data inventory and, only if a valid source exists, the screen. Do not turn data acquisition into a multi-day campaign by stealth.

## Data inventory — 2026-09-02

### Repository

No existing historical SPX/SPY option-chain/open-interest/gamma dataset or implemented dealer-GEX history was found in the repository search. Current daily SPY price history is sufficient for the response variable, not for the dealer-state predictor.

### Official / institutional historical sources

1. **Cboe DataShop Option EOD Summary** — historical data available from January 2012 to present. Provides strike/expiration/type, option prices, volume, open interest, and optional calculated IV/Greeks. This is sufficient in principle to construct a point-in-time gamma-by-strike/open-interest proxy. It is a commercial DataShop product, not established as free.
2. **Cboe DataShop Option Quotes** — interval quote summaries with optional open interest and calculated Greeks. Also sufficient in principle, but much larger and commercial; unnecessary for the first daily sandbox test if EOD data can be obtained.
3. **OptionMetrics IvyDB US** — comprehensive institutional EOD US equity/index option history from 1996 onward, including open interest and calculated Greeks. Suitable but institutional/commercial; not a quick free-data path.

### Public Cboe historical page

Cboe's public historical-options download exposes historical **volume** aggregation. It does not expose the strike-by-expiration open-interest plus gamma history needed to reconstruct the proposed dealer-state proxy. It is therefore insufficient for this screen.

### Third-party API leads

QuantData documents historical per-session open-interest rollups and per-strike snapshots; OptionChainIQ documents historical full-chain snapshots including OI and Greeks. Neither is treated as available/free until account access, historical depth, licensing, and reproducibility are verified. They are leads, not approved sources.

## Methodological boundary

Open interest does **not** reveal dealer direction by itself. A common GEX construction that assumes dealers are short customer calls and long customer puts is a model assumption, not observed inventory. Any sandbox implementation must label that assumption explicitly and test robustness to alternative sign conventions or use a source that provides defensible directional-flow information.

Cboe states that intraday open-interest fields use the previous night's OCC end-of-day OI and remain static until the next morning. Any point-in-time daily state must respect that publication timing; same-day end-of-day OI may not be treated as known before it was published.

## Current classification

`SCREEN_INCONCLUSIVE — DATA BLOCKED`

Reason: the mechanism is strong enough to screen, but the repository and confirmed free official sources do not currently provide causal historical strike-by-expiration SPX/SPY open interest plus gamma/delta data. No synthetic VIX proxy, current-chain backfill, or hindsight reconstruction is authorized merely to produce a backtest.

## Cheapest next evidence

Before purchasing institutional history, determine whether an existing operator account/trial can provide a modest point-in-time daily SPY or SPX chain sample with: session date, expiration, strike, call/put, open interest, underlying price, and either gamma/IV or sufficient quote fields to calculate gamma. Minimum useful sandbox span should cover multiple market regimes; a short recent sample may test plumbing but cannot support a substantive screen verdict.
