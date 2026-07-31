# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

**Classification:** Research-only confirmation following Campaign #48 discovery

**Status:** PROSPECTIVE SOURCE ACCUMULATION — methodology locked; initial post-2025 source published; deterministic source-maintenance utility validated; confirmation computation remains prohibited until the final cumulative source satisfies every locked sample gate

**Governance branch:** `agent/campaign-49-btc-volatility-state-confirmation-governance`

**Repository:** `IteraDynamics/ID_test`

**Governed lineage base:** Campaign #48 closure `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Governing method:** `docs/research/BTC_VOLATILITY_STATE_AND_DRAWDOWN_CONFIRMATION.md`

**Methodological design lock:** `9203b6f20983b8c168182e6bc58135f4f7d5913c`

**Source-maintenance implementation GO:** `e5d53c1997738790ba286abe4dd4f7656bf89be7`

**Source updater implementation:** `57c70731309300791b12203011b84caf28b502d9`

**Source updater tests:** `7fced0696969609bf0a21c11609c110b96a22934`

## Objective

> Do the volatility-state persistence and drawdown-linked future-volatility associations discovered in Campaign #48 survive an honestly independent, prospectively untouched confirmation sample?

Campaign #49 is confirmation, not discovery. It carries forward exactly 15 Campaign #48 associations across five scientific groups and does not reopen directional-return research.

## Locked method

The design lock fixes before Campaign #49 outcomes:

- Coinbase Exchange `BTC-USD` as the sole provider and product;
- cumulative post-2025 hourly source protocol;
- exactly three predictors and two outcome families;
- exactly 15 candidates and expected signs;
- horizon-specific non-overlapping 24-, 72-, and 168-hour anchor grids;
- OLS with one standardized predictor, intercept, HC3 covariance, and no controls or interactions;
- minimum gates of 180, 90, and 52 candidate-complete anchors by horizon;
- Holm family-wise correction across all 15 candidates;
- a fixed Campaign #48 effect-size compatibility band of 0.25x through 4.0x absolute discovery coefficient with the same sign;
- two-of-three horizon group confirmation;
- three-of-five campaign confirmation including at least one M and one V group;
- deterministic failure precedence and exactly ten future canonical outputs;
- preflight, two-run byte-identical replay, and source immutability requirements.

The final cumulative source bytes and source annex remain intentionally unfrozen until the untouched sample is mature. The later source annex may identify source bytes and coverage only; it may not alter the locked method.

## Initial prospective source publication

Published files:

1. `data/btcusd_3600s_2026-01-01_to_2026-07-31.csv`
   - Git blob: `41c7489df6830eede734b867962eb91616ea036b`
   - SHA-256: `7af947322b878aee905fb4bd2643f4dec6e9bf0a78551c31a092899c4b8d38ce`
   - bytes: `350,460`
   - rows: `5,073`
2. `data/btcusd_3600s_2026-01-01_to_2026-07-31.source_manifest.json`
   - Git blob: `0b80a70503caa45c32ddd7afd7c9f420f56a422a`

Source evidence:

- provider: Coinbase Exchange;
- product: `BTC-USD`;
- granularity: `3600` seconds;
- first timestamp: `2026-01-01 00:00:00`;
- last timestamp: `2026-07-31 13:00:00`;
- continuous hourly positions: `5,078`;
- exact schema: `timestamp,open,high,low,close,volume`;
- source validation: `PASS`;
- governed missing timestamps: exactly `2026-05-08 02:00:00` through `2026-05-08 06:00:00` inclusive;
- no Campaign #49 predictor, outcome, anchor, regression, p-value, or result was generated or inspected.

## Source-maintenance validation evidence

The source-only updater is:

`scripts/update_campaign49_coinbase_source.py`

The synthetic focused suite passed:

`12 passed in 0.61s`

The module entry point was also verified successfully:

`python -m scripts.update_campaign49_coinbase_source --help`

Validated behavior includes:

- fixed start `2026-01-01T00:00:00Z` and explicit whole-hour end;
- exact ordered schema and LF-only canonical CSV serialization;
- prior source-manifest hash reconciliation;
- timestamp, ordering, duplicate, alignment, OHLCV, and endpoint validation;
- complete missing-hour inventory without repair;
- fail-closed detection of changed historical values;
- fail-closed detection of disappeared prior candles;
- fail-closed detection of newly appearing candles inside a previously frozen gap;
- deterministic source-only manifest generation;
- no predictor, outcome, anchor, regression, p-value, or confirmation-result computation.

## Data maturity

As of July 31, 2026, the source cannot meet the locked 52-anchor 168-hour gate. Even perfect coverage could provide at most 29 non-overlapping 168-hour observations after lookback and outcome requirements.

Confirmation computation remains prohibited until a final cumulative source meets every locked gate. Coverage into approximately January 2027 is required, and missing windows may delay maturity.

## Current authorization

**Decision:** Continue prospective Coinbase source accumulation through the validated source-only updater. No confirmation computation is authorized.

Authorized now:

- use `scripts/update_campaign49_coinbase_source.py` to create later cumulative Coinbase snapshots from the fixed start;
- run the focused source-updater tests after any updater change;
- validate source identity, provenance, timestamps, OHLCV values, endpoints, missing-hour inventory, hashes, and prior-interval immutability;
- present each proposed cumulative snapshot for publication review before committing it;
- update this board with source-only evidence;
- make pre-outcome corrections only if separately recorded before any confirmation computation.

Not authorized:

- Campaign #49 predictor or outcome calculation;
- confirmation anchor construction;
- regression, p-value, Holm, compatibility, group, or campaign-result computation;
- confirmation runner or result artifacts;
- historical sensitivity outcomes;
- economic-value testing or Core v1 comparison;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Immediate sequence

1. Branch from Campaign #48 closure. **Completed.**
2. Draft Campaign #49 confirmation design. **Completed.**
3. Select Coinbase and acquire the initial prospective source. **Completed.**
4. Publish and reconcile the initial source. **Completed.**
5. Lock the methodological design before Campaign #49 outcomes. **Completed: `9203b6f`.**
6. Implement the source-only cumulative reconciliation utility. **Completed: `57c7073`.**
7. Validate the source-only utility. **Completed: `12 passed in 0.61s`; module entry point verified.**
8. Continue prospective source accumulation without confirmation computation. **Active.**
9. Freeze the final cumulative source annex only after all sample gates are met. **Not yet feasible.**
10. Freeze a separate confirmation implementation handoff and record a separate implementation GO before any confirmation computation. **Not authorized.**

## Campaign #48 completion record

**Campaign:** Campaign #48 — Simple BTC Price-State Predictive Baselines

**Final status:** COMPLETE — 15 supported research associations under the frozen discovery design

**Closure:** `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Canonical publication:** `fd7ee01`

Campaign #48 found reproducible association between recent BTC volatility/drawdown information and future movement magnitude/volatility, but not direction. It authorized no runtime or strategy change.
