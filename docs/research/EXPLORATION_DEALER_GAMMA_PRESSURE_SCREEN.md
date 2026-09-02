# Exploration Screen — Index-Options Dealer Gamma Pressure

**Status:** FREE SOURCE IDENTIFIED / OCC RECONCILIATION PENDING
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

A public preservation mirror of the Philipp Dubach historical options dataset is available on GitHub and exposes yearly SPY Parquet files covering **2008-2025**. The published schema contains exactly the fields needed for a sandbox dealer-gamma proxy:

- observation `date`;
- `expiration`;
- `strike`;
- call/put `type`;
- `open_interest`;
- `implied_volatility`;
- `gamma`;
- bid/ask/volume and additional Greeks.

The mirror states that SPY contains about **24.7 million contract-day rows** across roughly 4,500 trading days. A public preservation mirror describes the rows as end-of-day chain observations and says files were recovered from surviving Git LFS storage with hashes checked against the original LFS pointers.

This clears the **cost/access** blocker for sandbox purposes: no paid data subscription is required to attempt the screen.

### Provenance caveat

This is not an exchange-certified or institutional vendor dataset. The upstream dataset's underlying market-data sourcing is not sufficiently documented for confirmation-grade use. Therefore:

- it is acceptable only for a cheap sandbox screen after structural validation;
- it is not accepted as future confirmation/production-grade evidence merely because it is large;
- any promoted campaign would need a fresh source-governance decision.

### OCC official reference

OCC publicly exposes a daily open-interest batch endpoint and states that displayed/reported open interest is derived from the **previous day's settlement**. For example, an OCC report date of 2024-01-03 should reconcile to the mirror's 2024-01-02 observation, not to 2024-01-03 itself.

That timing convention is the causal boundary for this screen. A failure to reconcile OI semantics is `SCREEN_INVALID`, not a negative alpha finding.

### Commercial/institutional sources — not pursued

Cboe DataShop and OptionMetrics remain suitable higher-grade sources but are outside the operator's zero-dollar sandbox constraint and are not being pursued.

## Methodological boundary

Open interest does **not** reveal dealer direction by itself. A common GEX construction that assumes dealers are short customer calls and long customer puts is a model assumption, not observed inventory. Any sandbox implementation must label that assumption explicitly and test at least two sign conventions rather than selecting the one that produces the better result.

The first screen must therefore separate two questions:

1. **Does aggregate option gamma/open-interest geometry contain information about subsequent SPY path behavior?**
2. **Does a specific dealer-sign convention improve that separation in the theoretically expected direction?**

A result that exists only under one arbitrary sign convention is not enough for `SCREEN_POSITIVE`.

## Source-validation implementation

`scripts/probe_free_options_history.py` implements the reproducible mirror source gate. For a selected year it:

1. downloads one yearly SPY Parquet file from the public preservation mirror;
2. records byte size and SHA-256;
3. verifies Parquet magic bytes and required columns;
4. reports date/expiration/strike breadth;
5. inventories missing OI, gamma, and IV;
6. fails closed on invalid call/put types, negative OI, or expiration-before-observation rows;
7. writes a deterministic JSON validation report under `artifacts/free_options_history_probe/`.

No runtime, strategy, portfolio, NAV, order, or exposure path is touched.

## Multi-year structural validation — PASS

Three deliberately different years were checked: modern 2024, crisis 2020, and earliest-history 2008.

### 2024

- status `USABLE`;
- 2,292,800 rows;
- 253 dates, 286 expirations, 495 strikes;
- 0 missing OI/gamma/IV;
- 0 invalid type, negative OI, or expiry-before-observation rows;
- 479,442 zero-OI rows;
- SHA-256 `d9bf7c14b5bfb01cf03bc413773d30eee14026afc377e2daf3d0691a92a0b38d`.

### 2020

- status `USABLE`;
- 2,346,116 rows;
- 252 dates, 194 expirations, 460 strikes;
- 0 missing OI/gamma/IV;
- 0 invalid type, negative OI, or expiry-before-observation rows;
- 463,377 zero-OI rows;
- SHA-256 `4e69fbbcb55139a84a3d58b85c87982fce52ec3044cbb510d422c4061aa1e5eb`.

### 2008

- status `USABLE`;
- 515,605 rows;
- 253 dates, 32 expirations, 190 strikes;
- 0 missing OI/gamma/IV;
- 0 invalid type, negative OI, or expiry-before-observation rows;
- 92,935 zero-OI rows;
- calls 257,941 vs puts 257,664 (not forced symmetry; accepted as observed early-history structure);
- SHA-256 `78acbfa15264b197b4bf77dca5f8f03d218a440249259d9d6d28f1f7a1f21194`.

Interpretation: the public mirror is internally coherent across modern, crisis, and earliest-history samples. Structural validation is complete. This does not by itself establish that its OI observation-date semantics match OCC.

## OCC reconciliation implementation

`scripts/reconcile_free_options_oi_with_occ.py` is the final pre-alpha source-governance probe. It:

1. downloads OCC's official daily open-interest CSV for a selected report date;
2. records the OCC payload SHA-256 and raw CSV;
3. normalizes supported OCC schema variants without silently guessing unresolved fields;
4. filters SPY and constructs expiration/strike/call-put/open-interest keys;
5. loads the mirror for an explicitly supplied prior trading date;
6. compares common contract keys and exact OI values;
7. returns `RECONCILES` only with at least 100 common contracts, >=95% exact OI identity, and >=80% OCC-key overlap.

If OCC changes the historical CSV schema in a way the probe cannot resolve, it returns the observed columns and `OCC_SCHEMA_UNRESOLVED_OR_NO_SYMBOL_ROWS` rather than fabricating a comparison.

## Current classification

`SCREEN_INCONCLUSIVE — OCC RECONCILIATION PENDING`

The multi-year structural source gate is now complete. The only remaining source-governance condition before constructing the gamma-pressure alpha screen is one successful OCC prior-settlement reconciliation.

## Next evidence

With the already-downloaded 2024 mirror file, run:

```powershell
python scripts/reconcile_free_options_oi_with_occ.py --occ-report-date 2024-01-03 --mirror-date 2024-01-02 --year 2024
```

OCC states that the 2024-01-03 report reflects OI following the previous trading day's settlement, so 2024-01-02 is the causal mirror comparison date. If this returns `RECONCILES`, source validation is sufficient for sandbox alpha construction. If it returns a schema diagnostic, inspect that diagnostic and adapt only the parser—not the economic hypothesis. If it returns a genuine OI mismatch after correct schema resolution, classify the data path `SCREEN_INVALID` and stop.
