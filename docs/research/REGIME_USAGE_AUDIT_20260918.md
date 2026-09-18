# Regime Usage Audit — 2026-09-18

## Status

**ACTIVE — observation-only repository audit.**

This audit was opened after the RRE research established additional continuous state information beyond Core's categorical label, while the first frozen PCA4 economic-use mechanism failed. That failed mechanism was not a replication of canonical Core v1 and therefore does **not** establish that RRE cannot improve Core v1.

No production, paper-trading, runtime, strategy, portfolio, threshold, order, NAV, exposure, execution, allocation, or Core-label behavior is changed or authorized by this audit.

## Question

Across the meaningful strategy/research work in this repository, what regime/state machinery was actually used?

Classify each family as:

1. **AUTHENTIC_CORE_REGIME** — consumes the same `BaselineRegimeEngine` label used by canonical Core plumbing.
2. **CORE_LABEL_CONSUMER** — strategy logic consumes `RegimeLabel`; execution through the standard research harness supplies `BaselineRegimeEngine` by default.
3. **INDEPENDENT_STATE** — uses a separately constructed state/regime/trend/volatility representation rather than Core's classifier.
4. **NO_CORE_REGIME** — no evidence that Core's classifier enters the tested strategy/research family.
5. **ATTRIBUTION_ONLY** — regime labels describe results but do not drive the strategy.
6. **UNCLEAR** — evidence insufficient; requires direct call-path inspection.

This is an implementation audit, not an economic result. Absence of Core regime use does not imply that adding it would improve a failed strategy.

## Canonical reference

The recovered Core lineage is already pinned in `docs/research/CORE_REGIME_REUSE_20260916.md`:

- `scripts/run_core_v1_paper_live.py::classify_regime` calls `BaselineRegimeEngine().classify_bar(...)` and passes the label into `StrategyContext`.
- `scripts/run_multi_strategy_walkforward.py` uses `run_backtest` without an engine override.
- `research/harness/backtest_engine.py` therefore instantiates `BaselineRegimeEngine()` and calls `classify_dataframe`.
- Core trend-following descendants consume the label for entries, blocked regimes, add-ons, and exits.
- Core's equity/gold logic and allocation contain additional machinery; the generic classifier is not the whole Core system.

For this audit, "Core regime" means this exact `BaselineRegimeEngine` lineage, not any code or document that happens to use the words regime, state, trend, or volatility.

## Findings

### A. Canonical/legacy research strategy library — Core regime is genuinely in the call path

**Classification: CORE_LABEL_CONSUMER / AUTHENTIC_CORE_REGIME when executed through the standard harness.**

Direct code evidence:

- `research/harness/backtest_engine.py` defaults to `BaselineRegimeEngine()`, precomputes its labels, and injects the current label into every `StrategyContext`.
- `research/strategies/trend_following.py` explicitly gates entry on `TREND_UP` and exits on `TREND_DOWN` / `HIGH_VOL`.
- `research/strategies/volatility_breakout.py` uses Core labels for allowed entry states and a `HIGH_VOL` exit.
- `research/strategies/crash_short_v6.py` requires `TREND_DOWN` for entry and uses Core labels in cover logic, while adding separate cross-asset SPY logic.
- Repository search shows `research.regimes` imports throughout the legacy trend-following, mean-reversion, volatility-breakout, crash-short, and short-trend strategy families.

**Implication:** a substantial portion of the older strategy library really was developed with Core's categorical regime classifier in the research harness. The user's prior assumption was therefore partly correct.

### B. Core v1 itself — authentic Core regime plus substantial non-regime machinery

**Classification: AUTHENTIC_CORE_REGIME.**

The recovered lineage confirms the paper/live and historical research plumbing use the same existing `BaselineRegimeEngine` class for the generic label. Core v1 nevertheless includes much more than that classifier: trend rules, cross-asset states, equity/gold rules, allocation, execution, cash behavior, and other sleeve-specific logic.

**Implication:** "replace the regime engine in Core v1" cannot be modeled faithfully by a generic TREND_UP=long / TREND_DOWN=short proxy.

### C. Core v1 regime-attribution work — NOT the Core classifier

**Classification: ATTRIBUTION_ONLY / INDEPENDENT_STATE.**

`research/trade_idea_radar/CORE_V1_REGIME_ATTRIBUTION.md` explicitly says its initial regime labels are "deliberately deterministic and simple" and "not a classifier or model-selection layer." It creates separate equity, crypto, volatility, drawdown, calendar-year, and stress-window buckets to attribute already-generated Core v1 NAVs.

Those buckets do not establish that Core's classifier drove the allocation comparison.

**Implication:** repository references to "Core v1 regime attribution" must not be counted as evidence that the authentic Core regime engine was the conditioning mechanism under test.

### D. Crash-short family / Campaign #54 — authentic Core label is part of strategy logic

**Classification: CORE_LABEL_CONSUMER, with additional independent cross-asset state.**

`crash_short_v6` requires Core `TREND_DOWN` for entry and uses Core labels for exits, but also adds a SPY SMA175 macro-bear gate. Campaign #54 documentation is among the small set of post-Core research documents that explicitly references `BaselineRegimeEngine`.

**Implication:** this is an example of a later strategy family that did use Core regime information while layering another state variable on top.

### E. Fresh ETF strategy discovery (2026-09-14) — no Core regime engine in the strategy package

**Classification: NO_CORE_REGIME / INDEPENDENT_STATE depending on candidate.**

Repository search finds no `research.regimes` or `RegimeLabel` dependency in `research/fresh_discovery`. The campaign tested independent hypotheses such as dual momentum, sector residual reversal, and trend-conditioned pullbacks.

**Implication:** the fresh ETF failure cannot be described as "these ideas were tested using Core's regime engine." They were separate strategy constructions.

### F. Fresh crypto discovery / long-history / forward research — independent state machinery

**Classification: INDEPENDENT_STATE.**

Repository search finds no `RegimeLabel` dependency in `research/fresh_crypto`. The campaign board describes trend ensembles, breakout, rotation, volatility caps, and later a fixed state rule. Those are separate constructions, not calls to Core's `BaselineRegimeEngine`.

**Implication:** the fresh crypto strategy line did **not** receive Core's regime classifier simply because it used the words trend/state.

### G. Fresh crypto ML allocation — independent learned allocation/state

**Classification: INDEPENDENT_STATE / NO_CORE_REGIME.**

The ML allocator was built around features predicting relative future wealth of fixed trend and allocation portfolios. Repository search finds no Core `RegimeLabel` dependency in the fresh-crypto package.

**Implication:** its negative ML result is not evidence against Core-regime-conditioned ML or against RRE.

### H. Broad ML development program (2026-09-09 through 2026-09-11) — no direct Core classifier dependency located

**Classification: NO_CORE_REGIME for the inspected `research/ml_development` package; individual historical-regime studies remain separate.**

Repository search finds no `research.regimes` / `BaselineRegimeEngine` dependency in `research/ml_development` or `research/ml_lab`. Those programs used their own features, cross-sectional states, macro interactions, ranking, volatility, breadth, and portfolio mappings.

Separate historical-regime research modules do explicitly study Core/historical state sequences; those should not be conflated with the ML strategy/economic experiments.

**Implication:** much of the broad ML research did not simply inherit Core's regime engine.

### I. Campaigns built around non-price information (funding/basis, COT, rates, etc.)

**Classification: NO_CORE_REGIME unless a campaign-specific call path proves otherwise.**

The campaign designs are deliberately independent signal families. Repository search does not show `BaselineRegimeEngine` in the campaign runner family; the explicit exception found is Campaign #54 crash-short.

**Implication:** their null/negative findings remain findings about those hypotheses, not tests of whether Core/RRE conditioning could rescue them.

### J. RRE research (2026-09-16 onward)

**Classification: AUTHENTIC_CORE_REGIME as baseline/reference + research-only continuous extensions.**

The RRE line deliberately recovered Core's exact classifier and then tested information beyond it:

- exact Core reuse;
- multidimensional state;
- PCA compression;
- latent trajectories;
- transition geometry;
- Core stability;
- conditional market behavior;
- first PCA4 economic-use mechanism.

The evidence to date supports a layered representation:

- Core label: semantic categorical state;
- PCA4: continuous state/risk coordinates;
- stability/trajectory: transition-instability information.

The first frozen economic mechanism — inverse-risk scaling of a simplified Core-label directional proxy — failed. It was not canonical Core v1 replication and does not close the broader RRE/Core-v1 integration question.

## Preliminary audit conclusion

The repository does **not** support the blanket statement that all post-Core strategy research used Core's regime engine.

The opposite blanket statement is also wrong.

The actual history is mixed:

- the older standard research harness and many legacy strategy families genuinely consume the authentic Core classifier;
- crash-short retained it and added cross-asset conditioning;
- several later "fresh" strategy, crypto, and ML programs used independent state/feature constructions and did not call the Core classifier;
- some documents use "regime" only for attribution or descriptive bucketing;
- the current RRE line is the first recent program explicitly centered on recovering the exact Core classifier and measuring information beyond it.

This means prior strategy failures cannot all be interpreted as failures **after conditioning on the strongest known Core/RRE state representation**.

It also does not justify automatically reopening every failed strategy. Re-evaluation should be selective and hypothesis-driven.

## Next audit phase before any new P&L experiment

1. Build a strategy-family inventory from actual executable call paths, not document terminology.
2. For each economically tested family, record:
   - runner / strategy entry point;
   - whether `BaselineRegimeEngine` is instantiated or inherited through the harness;
   - which exact `RegimeLabel` values affect entry, exit, sizing, or blocking;
   - any independent state/regime features;
   - whether regime is causal input or attribution-only;
   - final research disposition.
3. Identify only those failed/weak families where:
   - Core/RRE state was absent;
   - the economic hypothesis has a plausible state dependence;
   - revisiting it would test a new predeclared interaction rather than post-hoc tuning.
4. Separately establish a canonical Core v1 reproduction control before any claim that RRE improves or fails to improve Core v1.

No RRE-to-Core integration rule is authorized by this audit.
