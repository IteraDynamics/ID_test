# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

## Active campaign

**Campaign:** Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

**Classification:** Research-only confirmation following Campaign #48 discovery

**Status:** INITIAL SOURCE SNAPSHOT VALIDATED LOCALLY — exact Coinbase BTC-USD source identity recorded; publication of the source CSV and source manifest only is authorized; no confirmation predictors, outcomes, anchors, models, results, economic tests, runtime work, or strategy work authorized

**Governance branch:** `agent/campaign-49-btc-volatility-state-confirmation-governance`

**Repository:** `IteraDynamics/ID_test`

**Governed lineage base:** Campaign #48 closure `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Draft governing specification:** `docs/research/BTC_VOLATILITY_STATE_AND_DRAWDOWN_CONFIRMATION.md`

**Design authorization:** `098ebe95e36783148789228b0a31cea0ae10591b`

**Initial draft:** `0c47262b9d4f0335f1568e785e000197c0be7bcf`

**Source-selection and feasibility commit:** `0359058bd2628202d7d6e502ce9fec5a9a700fa2`

**Source-acquisition authorization:** `21a5d6f5a74cf34b355fb67546c9f7952088a362`

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

## Initial governed snapshot evidence

The fixed initial snapshot was acquired locally under the authorized command for:

- start: `2026-01-01T00:00:00Z`;
- end: `2026-07-31T13:00:00Z`;
- product: `BTC-USD`;
- granularity: `3600`;
- local source path: `data/btcusd_3600s_2026-01-01_to_2026-07-31.csv`;
- local manifest path: `data/btcusd_3600s_2026-01-01_to_2026-07-31.source_manifest.json`.

Source-only validation evidence:

- source validation status: `PASS`;
- SHA-256: `7af947322b878aee905fb4bd2643f4dec6e9bf0a78551c31a092899c4b8d38ce`;
- byte count: `350,460`;
- data rows: `5,073`;
- continuous hourly positions implied by endpoints: `5,078`;
- first timestamp: `2026-01-01 00:00:00`;
- last timestamp: `2026-07-31 13:00:00`;
- exact ordered schema: `timestamp,open,high,low,close,volume`;
- whole-hour alignment: passed;
- uniqueness and strict ordering: passed;
- finite positive OHLC and nonnegative volume: passed;
- complete governed missing-hour count: `5`.

Exact missing timestamps:

1. `2026-05-08 02:00:00`;
2. `2026-05-08 03:00:00`;
3. `2026-05-08 04:00:00`;
4. `2026-05-08 05:00:00`;
5. `2026-05-08 06:00:00`.

The observed gap is preserved as source identity. No repair, interpolation, filling, resampling, matching, shifting, or synthetic candle is permitted.

No Campaign #49 predictor, outcome, anchor, regression, candidate statistic, or result was generated or inspected during source acquisition or validation.

## Data-maturity finding

As of July 31, 2026, even perfect post-2025 hourly coverage can provide at most 29 complete non-overlapping 168-hour confirmation anchors after the required 168-hour predictor lookback and 168-hour forward outcome.

The proposed minimum is 52 complete 168-hour anchors. The 52nd weekly anchor requires source coverage through approximately `2027-01-07 00:00:00`, with missing windows potentially delaying maturity.

The minimum gate must not be reduced merely to run the campaign earlier.

## Campaign #48 findings entering confirmation

1. trailing 24-hour realized volatility positively associated with future absolute return at 24, 72, and 168 hours;
2. trailing 24-hour realized volatility positively associated with future realized volatility at 24, 72, and 168 hours;
3. trailing 168-hour realized volatility positively associated with future absolute return at 24, 72, and 168 hours;
4. trailing 168-hour realized volatility positively associated with future realized volatility at 24, 72, and 168 hours;
5. deeper drawdown from the trailing 168-hour high associated with higher future realized volatility at 24, 72, and 168 hours.

No Campaign #48 directional-return association was supported.

## Current authorization

**Decision:** GO to publish and reconcile the exact initial Coinbase source CSV and deterministic source manifest only.

Authorized now:

- commit exactly `data/btcusd_3600s_2026-01-01_to_2026-07-31.csv`;
- commit exactly `data/btcusd_3600s_2026-01-01_to_2026-07-31.source_manifest.json`;
- verify the GitHub-published bytes, source SHA-256, manifest values, exact five-gap inventory, and branch scope;
- update the draft specification and board with the publication commit after reconciliation;
- inspect Campaign #48 canonical results only for later design-freeze inputs.

Not authorized:

- calculating Campaign #49 predictors or outcomes;
- constructing confirmation anchors;
- fitting, ranking, or interpreting Campaign #49 candidates;
- changing the candidate inventory, formulas, horizons, expected signs, sample gates, or source provider;
- implementation module, confirmation runner, result artifacts, economic-value testing, Core v1 comparison, or sensitivity outcomes;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Immediate sequence

1. Branch from Campaign #48 closure. **Completed.**
2. Record Campaign #49 design authorization. **Completed: `098ebe9`.**
3. Draft the confirmation specification. **Completed: `0c47262`.**
4. Select provider and record current feasibility. **Completed: `0359058`.**
5. Authorize fixed initial source acquisition. **Completed: `21a5d6f`.**
6. Acquire and source-validate the exact initial Coinbase snapshot. **Completed locally: PASS.**
7. Publish exactly the source CSV and source manifest. **Authorized next.**
8. Reconcile the published files and record their publication commit. **Pending.**
9. Continue prospective accumulation under immutable reconciliation. **Pending.**
10. Freeze the final governing specification only when source identity and final design decisions are complete. **Not authorized yet.**
11. Freeze a separate implementation handoff and record implementation GO before any confirmation computation. **Not authorized yet.**

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
