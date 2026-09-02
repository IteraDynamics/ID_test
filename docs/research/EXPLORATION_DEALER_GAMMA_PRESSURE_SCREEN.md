# Exploration Screen — Index-Options Dealer Gamma Pressure

**Status:** FREE SOURCE IDENTIFIED / SOURCE VALIDATION PENDING
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

No existing historical SPX/SPY option-chain/open-interest/gamma dataset or implemented dealer-GEX history was found in the Itera repository search. Current daily SPY price history is sufficient for the response variable, not for the dealer-state predictor.

### Free historical source identified

A public preservation mirror of the Philipp Dubach historical options dataset is available on GitHub (`SaidBahaDev/options-dataset-hist`) and exposes yearly SPY Parquet files covering **2008-2025**. The published schema contains exactly the fields needed for a sandbox dealer-gamma proxy:

- observation `date`;
- `expiration`;
- `strike`;
- call/put `type`;
- `open_interest`;
- `implied_volatility`;
- `gamma`;
- bid/ask/volume and additional Greeks.

The mirror states that SPY contains about **24.7 million contract-day rows** across roughly 4,500 trading days. A separate public mirror describes the rows as end-of-day chain observations and says files were recovered from surviving Git LFS storage with hashes checked against the original LFS pointers.

This clears the **cost/access** blocker for sandbox purposes: no paid data subscription is required to attempt the screen.

### Provenance caveat

This is not an exchange-certified or institutional vendor dataset. A surviving mirror explicitly notes that the upstream dataset's underlying market-data sourcing was not fully documented. Therefore:

- it is acceptable only for a cheap sandbox screen after structural validation;
- it is not accepted as future confirmation/production-grade evidence merely because it is large;
- any promoted campaign would need a fresh source-governance decision.

### OCC official reference

OCC publicly exposes daily open-interest reports and series search. OCC states that reported open interest is derived from the **previous day's settlement**. That timing convention is the causal boundary for this screen: an OI state associated with trading date `t` must not be used earlier than it would have been observable under the prior-settlement publication rule.

The public dataset must be spot-checked against OCC on overlapping dates/series before any alpha result is interpreted. A failure to reconcile OI semantics is `SCREEN_INVALID`, not a negative alpha finding.

### Commercial/institutional sources — not pursued

Cboe DataShop and OptionMetrics remain suitable higher-grade sources but are outside the operator's zero-dollar sandbox constraint and are not being pursued.

## Methodological boundary

Open interest does **not** reveal dealer direction by itself. A common GEX construction that assumes dealers are short customer calls and long customer puts is a model assumption, not observed inventory. Any sandbox implementation must label that assumption explicitly and test at least two sign conventions rather than selecting the one that produces the better result.

The first screen must therefore separate two questions:

1. **Does aggregate option gamma/open-interest geometry contain information about subsequent SPY path behavior?**
2. **Does a specific dealer-sign convention improve that separation in the theoretically expected direction?**

A result that exists only under one arbitrary sign convention is not enough for `SCREEN_POSITIVE`.

## Source-validation implementation

`scripts/probe_free_options_history.py` now implements the first reproducible source gate. For a selected year it:

1. downloads one yearly SPY Parquet file from the public mirror;
2. records byte size and SHA-256;
3. verifies required columns;
4. reports date/expiration/strike breadth;
5. inventories missing OI, gamma, and IV;
6. fails closed on invalid call/put types, negative OI, or expiration-before-observation rows;
7. writes a deterministic JSON validation report under `artifacts/free_options_history_probe/`.

No runtime, strategy, portfolio, NAV, order, or exposure path is touched.

## Current classification

`SCREEN_INCONCLUSIVE — SOURCE VALIDATION PENDING`

This replaces the earlier `DATA BLOCKED` classification. A free candidate source now exists, but no dealer-gamma alpha result is authorized until the source probe returns structurally usable data and a small OCC timing/series spot-check is completed.

## Next evidence

Run:

```powershell
python scripts/probe_free_options_history.py --year 2024
```

If `USABLE`, repeat on one crisis-era year (2020) and one early-history year (2008 or 2009). If all three pass structural validation, proceed to the actual dealer-gamma sandbox screen with the OI timing lag enforced. If the mirror fails schema, chronology, or OCC reconciliation, classify the data path `SCREEN_INVALID` and park the idea without purchasing data.
