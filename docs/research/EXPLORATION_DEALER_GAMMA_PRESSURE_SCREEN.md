# Exploration Screen — Index-Options Dealer Gamma Pressure

**Status:** FREE SOURCE STRUCTURALLY VALIDATED / OCC HISTORICAL SERIES RECONCILIATION UNAVAILABLE / CAUSAL LAG FROZEN
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

### OCC official semantics and historical-reconciliation correction

OCC's public **Series Search** states that displayed open-interest figures are derived from the **previous day's settlement** and exposes current series/contract-date/strike call and put open interest.

The previously attempted OCC `daily-open-interest` batch endpoint was incorrectly assumed to be a historical series-level download. The operator run on 2026-09-02 showed the downloaded file begins with a title row such as `Daily Open Interest - January 2024`; the endpoint is a **monthly aggregate daily-open-interest report**, not a contract-level historical SPY file. It therefore cannot support an expiration/strike/type exact-match reconciliation.

The documented OCC Series Search batch interface accepts `symbolType` and `symbol` but does not expose a historical `reportDate` parameter. Therefore an exact free historical contract-level OCC reconciliation for 2024 cannot be performed through the documented public interface.

This is a correction to the source-governance plan, not an alpha result and not evidence that the mirror is wrong.

### Frozen causal timing rule

To remove ambiguity about whether the mirror's observation-date open interest reflects same-day EOD or prior-settlement OI, the sandbox will use a deliberately conservative timing rule:

> **Every dealer-gamma state computed from mirror observation date `t` is lagged by one full trading day before it may be associated with any forward return or path outcome.**

No state from observation date `t` may be used to explain or predict the return occurring on `t`.

This makes the screen causal under either plausible labeling convention:

- if mirror OI on `t` is prior-settlement OI, the extra day is conservative;
- if mirror OI on `t` is same-day EOD OI, the state is first actionable on `t+1`.

This lag is frozen before any dealer-gamma outcome is inspected and may not be relaxed after seeing results.

### Commercial/institutional sources — not pursued

Cboe DataShop and OptionMetrics remain suitable higher-grade sources but are outside the operator's zero-dollar sandbox constraint and are not being pursued.

## Methodological boundary

Open interest does **not** reveal dealer direction by itself. A common GEX construction that assumes dealers are short customer calls and long customer puts is a model assumption, not observed inventory. Any sandbox implementation must label that assumption explicitly and test at least two sign conventions rather than selecting the one that produces the better result.

The first screen must therefore separate two questions:

1. **Does aggregate option gamma/open-interest geometry contain information about subsequent SPY path behavior?**
2. **Does a specific dealer-sign convention improve that separation in the theoretically expected direction?**

A result that exists only under one arbitrary sign convention is not enough for `SCREEN_POSITIVE`.

## Source-validation implementation

`scripts/probe_free_options_history.py` implements the structural source gate. For a selected year it:

1. downloads one yearly SPY Parquet file from the public preservation mirror;
2. records byte size and SHA-256;
3. verifies Parquet magic bytes and required columns;
4. reports date/expiration/strike breadth;
5. inventories missing OI, gamma, and IV;
6. fails closed on invalid call/put types, negative OI, or expiration-before-observation rows;
7. writes a deterministic JSON validation report under `artifacts/free_options_history_probe/`.

`scripts/reconcile_free_options_oi_with_occ.py` now correctly diagnoses the OCC aggregate report and records the frozen one-trading-day causal rule rather than pretending the aggregate file contains contract-level rows.

No runtime, strategy, portfolio, NAV, order, or exposure path is touched.

## Structural validation results

### 2024 — PASS

- 2,292,800 rows;
- 253 distinct trading dates;
- 286 distinct expirations;
- 495 distinct strikes;
- 0 missing OI/gamma/IV rows;
- 0 invalid call/put rows;
- 0 negative OI rows;
- 0 expiry-before-observation rows;
- SHA-256 `d9bf7c14b5bfb01cf03bc413773d30eee14026afc377e2daf3d0691a92a0b38d`.

### 2020 crisis year — PASS

- 2,346,116 rows;
- 252 distinct trading dates;
- 194 distinct expirations;
- 460 distinct strikes;
- 0 missing OI/gamma/IV rows;
- 0 invalid call/put rows;
- 0 negative OI rows;
- 0 expiry-before-observation rows;
- SHA-256 `4e69fbbcb55139a84a3d58b85c87982fce52ec3044cbb510d422c4061aa1e5eb`.

### 2008 earliest history — PASS

- 515,605 rows;
- 253 distinct trading dates;
- 32 distinct expirations;
- 190 distinct strikes;
- 0 missing OI/gamma/IV rows;
- 0 invalid call/put rows;
- 0 negative OI rows;
- 0 expiry-before-observation rows;
- SHA-256 `78acbfa15264b197b4bf77dca5f8f03d218a440249259d9d6d28f1f7a1f21194`.

Interpretation: the mirror is internally and structurally consistent across modern, crisis, and earliest-history samples. This remains sandbox-grade source validation, not confirmation-grade provenance.

## Current classification

`SCREEN_INCONCLUSIVE — SOURCE VALIDATED FOR SANDBOX / ALPHA SCREEN NOT YET RUN`

The free source is structurally usable across all three stress samples. Exact historical OCC contract-level reconciliation is unavailable through the attempted free batch endpoint, so the conservative one-trading-day lag above is now the governing causal safeguard.

## Next evidence

Build and run the actual dealer-gamma sandbox screen using:

- only mirror data that passed the structural gate;
- one full trading-day lag from mirror observation to usable state;
- next 1, 2, and 5 trading-day outcomes;
- a sign-free gamma/OI geometry measure plus at least two explicit dealer-sign conventions;
- shuffled-state negative controls;
- year/regime decomposition so a single crisis cannot dominate;
- no parameter tuning after outcome inspection.

A `SCREEN_POSITIVE` result only earns a governed campaign. It authorizes no Core v1 change, no Core v2 inclusion, no portfolio weight, and no paper/live action.
