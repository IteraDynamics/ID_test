# Regime Usage Audit — Phase 2 Executable-Path Inventory — 2026-09-18

## Scope and governance

This is an observation-only continuation of `REGIME_USAGE_AUDIT_20260918.md`. The authoritative campaign board was re-read on this branch before this phase.

No production, paper, runtime, strategy, portfolio, threshold, order, NAV, exposure, execution, allocation, or Core-label behavior is changed or authorized.

The purpose is narrower: distinguish research that actually consumed authentic Core regime labels from research that used independent state machinery, and identify whether any prior negative/weak strategy family poses a genuinely new RRE-conditioned hypothesis.

## Executable-path matrix

| Family / experiment | Executable path inspected | Core classifier in decision path? | Other state machinery | Regime role | Prior disposition | RRE revisit status |
|---|---|---:|---|---|---|---|
| Standard research harness | `research/harness/backtest_engine.py` | **YES** | strategy-specific indicators | supplies `BaselineRegimeEngine.classify_dataframe` into `StrategyContext` | infrastructure | reference path |
| Legacy trend following | `research/strategies/trend_following*.py` via standard harness | **YES** | EMA structure/momentum, later cross-asset rules | entry/exit/blocking/sizing tiers depending version | evolved into Core lineage | **do not treat as regime-naive** |
| Legacy mean reversion | `research/strategies/mean_reversion.py` via standard harness | **YES** | price/volatility indicators | strategy gate/decision input | historical research | **do not treat as regime-naive** |
| Legacy volatility breakout | `research/strategies/volatility_breakout.py` via standard harness | **YES** | ATR compression, breakout, volume | entry-state allow-list + HIGH_VOL exit | historical research | **do not treat as regime-naive** |
| Crash short v6 / Campaign #54 | `research/strategies/crash_short_v6.py` via Core-style harness | **YES** | SPY SMA175, EMA, drawdown, ATR, persistence | TREND_DOWN entry gate + regime exits | Core-v2 founding research; hindsight caveat | **already Core-conditioned** |
| Fresh ETF discovery | `research/fresh_discovery/run.py -> strategies.make_schedules/Features.raw` | **NO** | own trend, momentum, reversal, pullback, covariance/risk rules | none from Core | no OOS/MC promotion; 63d momentum retained only as comparator/diversification hypothesis | **eligible in principle** |
| Fresh crypto discovery | `research/fresh_crypto/run.py -> engine.schedules` | **NO** | 90/180/365 trend ensemble, breakout state, rotation, covariance/vol targeting | independent state | weak standalone economics | **eligible in principle** |
| Fresh crypto fixed state rule | forward/long-history family built on fresh-crypto machinery | **NO** | independent weekly state selector and fixed thresholds | independent defensive selector | useful development; weak 2025-2026 forward absolute economics | **possible but low priority** |
| Fresh crypto ML allocator | `research/fresh_crypto_ml/run.py -> features/models/portfolio` | **NO** | acceleration, trend agreement, volatility ratio, downside fraction, learned allocation | independent learned state | rejected promotion | **eligible in principle, but old target/model failure remains** |
| ML trend foundation | `research/ml_development/trend_foundation.py` | **NO** | 63/126/252 trend votes, group budgets, risk forecast | independent trend/risk state | fixed trend baseline useful; ML follow-on separate | **eligible in principle** |
| Broad ML development | `research/ml_development/run.py` | **NO** | ETF price/risk features and learned models | no Core classifier located | mixed/negative ML increments | **not automatically rescued by RRE** |
| ML lab | `research/ml_lab/*` | **NO direct dependency located** | experiment-specific price/macro/cross-sectional state | independent | experiment-specific | **case-by-case only** |
| Crypto reversal initial | `research/crypto_reversal/experiment.py` | **NO** | shock/stabilization signal | no Core state | rejected fixed spec for OOS/MC | superseded for this question by controlled Core-filter test |
| Regime reversal follow-up | `research/regime_reversal/experiment.py` | **YES — exact recovered Core reader** | original reversal signal + Core state filter | exact state fixed at signal completion; seven labels all reported | did not advance | **already tested with Core; RRE-only extension would be a new hypothesis** |
| Core v1 regime attribution | `research/trade_idea_radar/CORE_V1_REGIME_ATTRIBUTION.md` runner family | **NO as strategy driver** | simple equity/crypto/vol/drawdown/calendar buckets | attribution only | diagnostic | not a strategy-conditioning precedent |
| Campaign #51 conditional directional value | governed campaign implementation | **NO** | trailing volatility + drawdown interactions with recent return | independent continuous conditioning | valid development negative | **conceptually relevant RRE candidate, but frozen family itself stays closed** |
| Campaign #52 chronological state value | canonical Core replay/control family | Core strategy itself is canonical; experiment manipulates sleeve target chronology | sleeve-level pre-execution target state | tests chronology, not classifier replacement | development negative under frozen multiplicity gate; economically descriptive positive | **not a regime-naive strategy candidate** |
| Funding/basis, COT, rates and other non-price campaigns | campaign-specific runners/docs | **NO Core dependency located in campaign family search** except crash-short | non-price signal families | independent | campaign-specific | only revisit if a predeclared economic interaction with RRE is plausible |

## Evidence details

### 1. Standard harness really does inject authentic Core state

`research/harness/backtest_engine.py`:

- imports `BaselineRegimeEngine`;
- instantiates it when no override is supplied;
- calls `classify_dataframe(df)`;
- passes each resulting label into `StrategyContext(regime=...)`;
- calls the strategy only after that state has been assigned.

Therefore any strategy executed through this harness without an override is not regime-naive.

### 2. Legacy strategy modules use the label economically

Examples inspected directly:

- `trend_following.py`: requires `TREND_UP` for bullish entry; exits on `TREND_DOWN` or `HIGH_VOL`.
- `volatility_breakout.py`: allows entry only in a fixed Core-label set and exits in `HIGH_VOL`.
- `crash_short_v6.py`: requires `TREND_DOWN` before the remaining crash gates can fire; Core labels also enter cover logic.

These are not attribution tags. They change whether a position exists.

### 3. Fresh ETF discovery bypasses the Core harness entirely

`research/fresh_discovery/run.py` imports its own accounting, data, metrics and strategy scheduler. `strategies.py` constructs features and targets directly. Its trend rule is an independent price-vs-200-session-average test; momentum/reversal/pullback are independent feature families. There is no `research.regimes` import in this package.

The final result retained 63-session momentum only as a comparison/diversification hypothesis; sector reversal lost, pullback was turnover-heavy/low-return, and the blend was weak.

### 4. Fresh crypto uses a separate state system

`research/fresh_crypto/engine.py` constructs its own:

- 90/180/365-day trend ensemble;
- breakout state;
- rotation signal;
- covariance/volatility sizing.

No Core `RegimeLabel` dependency is present. The later fixed state rule and ML allocator inherit this independent research lineage rather than Core's classifier.

### 5. Broad ML work is also separate

`research/ml_development/run.py` imports the ETF-risk-screen feature machinery and uses return, trend, realized-volatility, drawdown and asset features with Ridge / gradient boosting / MLP models. No Core classifier dependency is present.

Likewise, repository search finds no `BaselineRegimeEngine` dependency in `research/ml_lab`.

This matters because "the ML work used regime/state features" is not equivalent to "the ML work was conditioned on Core's regime engine."

### 6. Reversal is a useful control case

The original crypto reversal experiment had no Core state. The immediate follow-up deliberately imported `CoreRegimeReader` and tagged each fixed signal with the exact recovered Core label available at signal completion.

That test improved the observed shape for `TREND_DOWN`:

- unfiltered: 1.43% CAGR, 0.172 Sharpe, -26.04% max drawdown, 115 trades;
- TREND_DOWN only: 1.84% CAGR, 0.477 Sharpe, -7.44% max drawdown, 29 trades.

But it still did not advance because the result was exposed development data, fragile to the five largest winners, uneven BTC/ETH, and all seven labels were inspected.

This is important evidence for the current question: **adding authentic Core state can materially change the economic shape of an otherwise weak strategy, but doing so after seeing the original failure does not create clean confirmation.**

### 7. Campaign #51 is conceptually adjacent but not an RRE test

Campaign #51 tested whether trailing 24h/168h BTC signed return became directionally informative conditional on trailing volatility or drawdown. It did not use Core/RRE state. All 12 frozen interactions failed development and the campaign is permanently closed under its own rules.

The negative therefore cannot be rewritten. A future RRE-conditioned directional interaction would have to be a separately chartered hypothesis, not a Campaign #51 rescue.

## What this changes

The audit changes the interpretation of the research history in three ways.

### A. We have already seen one concrete example where Core conditioning changed a weak strategy materially

The reversal follow-up is the clearest example. It does not prove RRE will create alpha, but it disproves the idea that regime conditioning is merely cosmetic.

### B. Several meaningful negative programs never saw authentic Core state

Most notably:

- fresh ETF momentum/reversal/pullback;
- fresh crypto trend/breakout/rotation and fixed state selector;
- fresh crypto ML;
- broad ETF ML development;
- Campaign #51's volatility/drawdown interaction family.

Their negative/weak results remain valid for the specifications tested. They are **not** evidence that the same economic mechanism has no conditional value inside the richer Core/RRE state representation.

### C. Re-running everything would still be bad research

RRE has now been developed after all of those outcomes were observed. Any selective revisit is development research and must explicitly account for that information exposure.

The correct question is not "can RRE rescue a loser?" It is:

> Does a predeclared economic mechanism have a reason to exist only in a particular continuous market state that the original strategy did not observe?

## Triage for a later RRE-conditioned experiment

### Tier A — strongest scientific candidates

**1. Fresh ETF 63-session momentum / diversified trend foundation**

Why it is interesting:

- trend already has modest positive economics rather than requiring RRE to manufacture an edge from a deeply negative base;
- Core/RRE state was absent;
- state-dependent trend efficacy is economically plausible;
- PCA4's strongest established information is future variance/movement intensity, which can plausibly alter the risk efficiency of an existing directional trend signal without inventing direction.

Constraint: any experiment must freeze the original trend signal and ask whether RRE changes **risk conditioning**, not search for favorable PCA regions.

**2. Fresh crypto plain trend / fixed state-rule family**

Why it is interesting:

- the independent state rule modestly improved development trend economics;
- forward results were weak in absolute terms, but this is direct evidence that state-dependent exposure matters to the mechanism;
- Core/RRE was absent;
- PCA4 is already demonstrated on BTC/ETH and therefore requires less cross-domain extrapolation.

Constraint: do not tune the old state-rule thresholds or use RRE to choose retrospectively between vol20/vol40. A new experiment would compare a fixed original trend control with a predeclared RRE-conditioned version.

### Tier B — scientifically valid but lower priority

**3. Crypto reversal + RRE continuous state**

Core TREND_DOWN already changed the strategy's observed risk shape, so a continuous-state extension is plausible. But the base family is fragile, low exposure, cost-sensitive, and already heavily exposed to development inspection. RRE should not be spent first on this family.

**4. Campaign #51-like directional conditioning**

The scientific question is attractive because Campaign #51 used crude volatility/drawdown states rather than RRE. But its original family is formally closed and the current RRE evidence still shows little directional-return information. A new directional RRE campaign therefore has a weaker prior than risk-conditioning an already-positive trend strategy.

### Tier C — do not reopen merely because RRE exists

- sector residual reversal;
- high-turnover ETF pullback;
- failed fresh-crypto learned allocator as originally targeted;
- generic ML architecture searches;
- independent non-price campaigns whose mechanism does not logically depend on price state.

RRE should not become a universal post-hoc filter attached to every negative result.

## Required control before claiming Core v1 improvement

The first PCA4 economic comparison used a simplified directional proxy:

- `TREND_UP = +1`;
- `TREND_DOWN = -1`;
- all other Core labels = 0;
- PCA4 only changed inverse-risk magnitude.

That experiment correctly rejected that **specific** mechanism.

It did not reproduce canonical Core v1, whose economic behavior includes multiple sleeves, strategy-specific indicators, cross-asset rules, allocation, cash behavior, execution, and authentic chronological target states.

Therefore the next Core-specific research milestone is not another PCA4 sizing rule. It is a **canonical Core v1 reproduction control** suitable for a later paired intervention.

Required properties:

1. exact existing Core strategy/sleeve logic;
2. exact existing Core regime classifier and parameters;
3. same historical inputs and chronology;
4. same allocation and execution assumptions;
5. deterministic replay identity against an already accepted Core artifact or canonical runner;
6. an explicit intervention seam where a future RRE variant can be substituted or added without changing anything else;
7. no RRE intervention until the control reproduces.

Only after that control exists can a frozen question such as "does adding RRE state to this exact decision seam improve canonical Core v1?" be interpreted cleanly.

## Phase-2 conclusion

The audit supports continuing RRE research.

It does **not** support indiscriminate strategy recycling.

The strongest next path is two-track:

- **Core track:** build the canonical Core v1 reproduction/control seam before another Core-vs-RRE economic test.
- **Research track:** preserve the two strongest regime-naive candidates — diversified/ETF trend and fresh-crypto trend/state — for separately frozen RRE-conditioning hypotheses after the Core control is established.

No economic experiment is authorized by this inventory alone.
