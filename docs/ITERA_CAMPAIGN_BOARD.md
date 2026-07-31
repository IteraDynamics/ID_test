# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

**Classification:** Research-only confirmation following Campaign #48 discovery

**Status:** SOURCE ACQUISITION GO — Coinbase Exchange BTC-USD selected; fixed initial snapshot and source manifest authorized; no confirmation predictors, outcomes, anchors, models, results, economic tests, runtime work, or strategy work authorized

**Governance branch:** `agent/campaign-49-btc-volatility-state-confirmation-governance`

**Repository:** `IteraDynamics/ID_test`

**Governed lineage base:** Campaign #48 closure `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Draft governing specification:** `docs/research/BTC_VOLATILITY_STATE_AND_DRAWDOWN_CONFIRMATION.md`

**Design authorization:** `098ebe95e36783148789228b0a31cea0ae10591b`

**Initial draft:** `0c47262b9d4f0335f1568e785e000197c0be7bcf`

**Source-selection and feasibility commit:** `0359058bd2628202d7d6e502ce9fec5a9a700fa2`

## Plain-English objective

> Do the volatility-state persistence and drawdown-linked future-volatility associations discovered in Campaign #48 survive an honestly independent, separately frozen confirmation design?

Campaign #49 is confirmation, not a second discovery sweep. It carries forward only the 15 supported Campaign #48 associations across five scientific groups. It does not reopen directional-return research.

## Selected source

The selected prospective confirmation provider is Coinbase Exchange.

- product: `BTC-USD`;
- official endpoint family: `https://api.exchange.coinbase.com/products/BTC-USD/candles`;
- granularity: `3600` seconds;
- repository acquisition utility: `scripts/fetch_coinbase_hourly_history.py`;
- ordered research schema: `timestamp,open,high,low,close,volume`;
- timestamp convention: timezone-naive UTC after parsing.

Coinbase one-hour candles are accepted only under exact reconciliation. Missing intervals are recorded, never repaired. No interpolation, filling, resampling, nearest-row matching, as-of matching, shifting, synthetic bars, or source substitution is permitted.

## Authorized initial snapshot

Acquire exactly:

- start: `2026-01-01T00:00:00Z`;
- end: `2026-07-31T13:00:00Z`;
- product: `BTC-USD`;
- granularity: `3600`;
- intended output: `data/btcusd_3600s_2026-01-01_to_2026-07-31.csv`.

The initial source manifest must record provider, endpoint family, product, acquisition command, fixed start and end, SHA-256, byte count, row count, exact schema, first and last timestamp, timezone convention, duplicate/order/alignment checks, OHLCV validity, continuous-hour count, and the complete missing-hour inventory.

Any warning or mismatch fails closed. The snapshot must not be repaired.

## Data-maturity finding

As of July 31, 2026, even perfect post-2025 hourly coverage can provide at most 29 complete non-overlapping 168-hour confirmation anchors after the required 168-hour predictor lookback and 168-hour forward outcome.

The proposed minimum is 52 complete 168-hour anchors. The 52nd weekly anchor requires source coverage through approximately `2027-01-07 00:00:00`, with any missing windows potentially delaying maturity.

The minimum gate must not be reduced merely to run the campaign earlier.

## Campaign #48 findings entering confirmation

1. trailing 24-hour realized volatility positively associated with future absolute return at 24, 72, and 168 hours;
2. trailing 24-hour realized volatility positively associated with future realized volatility at 24, 72, and 168 hours;
3. trailing 168-hour realized volatility positively associated with future absolute return at 24, 72, and 168 hours;
4. trailing 168-hour realized volatility positively associated with future realized volatility at 24, 72, and 168 hours;
5. deeper drawdown from the trailing 168-hour high associated with higher future realized volatility at 24, 72, and 168 hours.

No Campaign #48 directional-return association was supported.

## Current authorization

**Decision:** GO to acquire and validate the fixed initial Coinbase source snapshot only.

Authorized now:

- run the existing Coinbase hourly-history fetcher for the exact fixed window;
- validate source identity, schema, timestamps, duplicates, ordering, whole-hour alignment, OHLCV values, endpoints, and complete missing-hour inventory;
- calculate only source-level metadata and hashes;
- create and commit the source CSV and a deterministic source manifest;
- update the draft specification and board with source evidence;
- inspect Campaign #48 canonical results only for future design freeze inputs.

Not authorized:

- calculating Campaign #49 predictors or outcomes;
- constructing confirmation anchors;
- fitting, ranking, or interpreting Campaign #49 candidates;
- changing the candidate inventory, formulas, horizons, expected signs, or source provider;
- implementation module, confirmation runner, result artifacts, economic-value testing, Core v1 comparison, or sensitivity outcomes;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Immediate sequence

1. Branch from Campaign #48 closure. **Completed.**
2. Record Campaign #49 design authorization. **Completed: `098ebe9`.**
3. Draft the confirmation specification. **Completed: `0c47262`.**
4. Select provider and record current feasibility. **Completed: `0359058`.**
5. Acquire the exact initial Coinbase source snapshot. **Authorized next.**
6. Validate and freeze its source manifest without confirmation outcomes. **Pending.**
7. Continue prospective accumulation under immutable reconciliation. **Pending.**
8. Freeze the final governing specification only when source identity and final design decisions are complete. **Not authorized yet.**
9. Freeze a separate implementation handoff and record implementation GO before any confirmation computation. **Not authorized yet.**

## Campaign #48 completion record

**Campaign:** Campaign #48 — Simple BTC Price-State Predictive Baselines

**Final status:** COMPLETE — canonical artifacts published; 15 supported research associations under the frozen discovery design

**Implementation branch:** `agent/campaign-48-simple-btc-price-state-baselines-implementation`

**Closure commit:** `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Canonical artifact publication:** `fd7ee01`

Completed evidence:

- corrected focused suite: `27 passed`;
- governed preflight: `PASS` with outcomes `false`;
- exact governed missing-hour inventory: `36`;
- anchors: `403`;
- partitions: `135`, `134`, `134`;
- candidates: `72`;
- rankable: `72`;
- supported research associations: `15`;
- two canonical runs replayed byte-identically;
- governed source bytes remained unchanged;
- full suite: `531 passed`, `75 warnings`;
- no runtime or strategy surface changed.

Campaign #48 conclusion:

Simple recent BTC volatility and drawdown information contained reproducible association with the magnitude and volatility of subsequent movement, but not direction. The findings require separately frozen confirmation before any economic-value or Core v1 comparison.

## Historical carryover

Campaign #47 completed historical regime-structure discovery with zero rankable candidates and zero supported associations.

Campaign #45 completed historical regime-transition discovery with zero supported exact ordered-transition associations.

Campaign #46 completed the full historical regime-state source.

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #49 unless separately authorized.
