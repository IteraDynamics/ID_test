# Campaign #50 — Hypothesis-Family Selection

## Status

**PLANNING DECISION — one primary family selected; no Campaign #50 outcomes generated or inspected.**

This memo records repository inventory and family selection before implementation, candidate construction, or access to 2025 confirmation outcomes.

## Inventory findings

### Available source surfaces

The repository and prior work contain:

- governed Coinbase hourly BTC history covering 2018 through 2025;
- Coinbase hourly ETH history covering materially the same period;
- daily SPY, QQQ, GLD, BIL and a broad set of sector, style, size, international, bond, and defensive ETF files;
- source-manifest patterns for daily market data;
- deterministic OHLCV loaders, validators, resampling, backtest, cost, turnover, replay, paper-broker, and paper-runtime infrastructure.

The exact Campaign #50 source files, hashes, first and last timestamps, schemas, and missing-session inventories remain to be frozen before implementation.

### Duplication and holdout-contamination findings

Several obvious families are unsuitable as the primary Campaign #50 family because their 2025 observations or closely related economic mappings have already participated in prior research:

- simple BTC price state, realized volatility, drawdown, momentum, range position, and related transformations were screened in Campaign #48;
- BTC/ETH relative-strength allocation was previously researched across 2019–2025;
- crash-short variants and long/short combinations were previously backtested across 2019–2025;
- jump-risk models and overlays were researched across daily assets and already have Core v1 monitoring and paper infrastructure;
- trend persistence and regime-transition/state families have already received substantial research attention;
- SPY/QQQ trend and defensive-cash mappings are already represented in Core v1 and prior equity-book work.

Reusing those families would weaken the claim that the 2025 terminal interval is an untouched confirmation holdout.

## Ranked hypothesis families

### Rank 1 — Equity breadth deterioration and recovery

**Role:** low-turnover equity exposure gate / risk-state signal.

**Hypothesis:** broad participation across economically distinct equity groups contains incremental information about subsequent SPY and QQQ return distribution beyond each index's own trend state.

Candidate concepts would be limited to a narrow prespecified family such as:

- fraction of a frozen ETF universe above its trailing moving average;
- breadth change over a frozen short window;
- cross-sectional dispersion of trailing returns;
- cyclical-minus-defensive participation or relative-strength breadth.

**Mechanism:** index-level prices can remain elevated while participation narrows. Broad deterioration may reveal weakening risk appetite before the cap-weighted index trend breaks; broad recovery may identify improving participation after stress.

**Novelty versus Core v1:** Core v1 primarily uses each traded index's own trend and macro state. It does not currently use a frozen cross-sectional breadth state derived from a broad equity universe.

**Holdout feasibility:** daily data provides roughly five development years, two validation years, and one untouched confirmation year. A 5–20 trading-day horizon can provide meaningful non-overlapping or carefully governed observations without waiting for new calendar time.

**Likely turnover:** low to moderate, suitable for daily rebalance or slower exposure gating.

**Economic path:** if statistically confirmed, map breadth state to a separately frozen SPY/QQQ exposure overlay and compare incrementally against the existing equity baseline under costs.

**Primary risks:** survivorship and universe-definition leakage, inconsistent source histories, correlated predictors, and accidental use of 2025 when defining the universe or thresholds.

### Rank 2 — BTC/ETH hour-of-week continuation and reversal

**Role:** short-horizon directional or execution-timing signal.

**Hypothesis:** fixed UTC hour-of-week states condition continuation or reversal after large recent moves because global liquidity and participant composition vary systematically through the week.

**Novelty versus Core v1:** Core v1 is trend/regime driven and does not use calendar microstructure.

**Holdout feasibility:** excellent hourly support across development, validation, and 2025 holdout.

**Likely turnover:** high; cost and slippage sensitivity would be substantial.

**Economic path:** only as a timing modifier or small satellite after statistical confirmation.

**Why not primary:** multiplicity and researcher degrees of freedom can expand quickly across 168 hour-of-week cells, assets, move thresholds, and horizons. The expected edge may be too small after realistic crypto costs.

### Rank 3 — Cross-asset defensive confirmation state

**Role:** equity exposure gate.

**Hypothesis:** relative movement among equities, Treasuries, gold, and cash-like instruments contains incremental information about future equity downside risk beyond SPY/QQQ trend alone.

**Novelty versus Core v1:** Core v1 holds defensive assets but does not fully use their relative behavior as an independent predictive state.

**Holdout feasibility:** daily source support should be adequate after exact coverage reconciliation.

**Likely turnover:** low.

**Economic path:** a defensive confirmation overlay for the equity sleeve.

**Why not primary:** prior multi-asset allocation, defensive-equity, and jump-risk work creates more conceptual overlap and a greater risk that 2025 indirectly influenced the hypothesis than for broad equity participation.

## Selection

**Selected primary family: Equity breadth deterioration and recovery.**

The selection is based on:

1. a plausible market-participation mechanism;
2. clear incremental distinction from Core v1's own-price trend logic;
3. low expected turnover and realistic cost tolerance;
4. direct mapping to the existing SPY/QQQ equity book if confirmed;
5. sufficient historical daily observations for immediate holdout-first testing;
6. lower 2025 contamination risk than previously researched crypto, jump-risk, relative-strength, crash-short, and defensive-allocation families.

## Required source-universe discipline

Before any outcome is generated, the governing specification must freeze:

- exact ETF universe and the non-performance-based reason each member is included;
- source provider, acquisition method, file path, hash, schema, first/last date, missing sessions, and duplicate checks for every file;
- development, validation, and untouched 2025 confirmation intervals;
- treatment of assets without complete coverage;
- a prohibition on selecting constituents based on Campaign #50 outcomes;
- a prohibition on replacing failed or incomplete constituents after outcome inspection.

A small, economically defined universe is preferred over a large data-mined universe. A provisional structure is broad index, size, style, and sector participation; the exact symbols remain unfrozen pending source reconciliation.

## Proposed statistical role

Campaign #50 should first test whether breadth state predicts future SPY/QQQ direction, downside, or absolute movement. It should not begin with a strategy backtest.

A successful statistical candidate would later enter a separate economic-value stage that freezes:

- signal-to-exposure mapping;
- comparator against the current equity baseline;
- transaction costs and rebalance cadence;
- turnover and exposure limits;
- pass/fail criteria;
- paper-trading eligibility requirements.

## Falsification

The family fails if prespecified breadth measures do not provide multiplicity-adjusted and directionally coherent information in development/validation and then fail the separately gated untouched 2025 confirmation test.

Failure also includes insufficient source coverage, unstable constituent availability, universe leakage, or an effect too small or too unstable to justify later economic testing.

## Authorization boundary

This memo selects the family only. It does not authorize:

- calculation of breadth predictors or future outcomes;
- access to Campaign #50 2025 outcomes;
- implementation;
- strategy mapping or backtesting;
- Core v1 comparison;
- paper trading;
- runtime or production changes.
