# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #48 - Simple BTC Price-State Predictive Baselines

**Classification:** Research-only predictive-baseline design over the frozen governed BTC hourly source

**Status:** DESIGN GO - specification drafting and freezing are authorized; predictive outcomes, implementation, result inspection, economic testing, and runtime changes remain prohibited

**Working branch:** `agent/campaign-48-simple-btc-price-state-baselines-governance`

**Repository:** `IteraDynamics/ID_test`

**Governed lineage base:** Campaign #47 closure `d8f8b234ccd342369d3d134e1dd7d7b916557b0a`

**Planned governing specification:** `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES.md`

## Plain-English objective

Campaign #48 asks a deliberately simple question:

> Does BTC's recent price behavior contain reliable information about what happens next?

Before Itera attributes predictive value to regimes, transitions, machine learning, or more complicated signal logic, it needs a transparent baseline showing what ordinary BTC price history can already explain.

The campaign will study a small, prespecified group of simple price-state concepts, expected to include:

- recent upward or downward price movement;
- the strength of recent movement;
- recent realized volatility;
- distance from a recent price average;
- position within a recent trading range;
- recent drawdown or related price-location measures.

The specification must define the exact formulas, trailing windows, horizons, outcomes, controls, support rules, chronological evaluations, multiplicity treatment, and failure conditions before any predictive outcomes are generated or inspected.

## What Campaign #48 is trying to learn

1. Whether transparent BTC price-state features contain reproducible information about future BTC behavior.
2. Whether future regime-derived candidates add information beyond ordinary momentum, volatility, and price-location effects.
3. What simple predictive hurdle later Itera candidates must exceed before economic or strategy-level testing is justified.

## Research role

Campaign #48 is a predictive-baseline discovery campaign.

It may evaluate statistical and chronological predictive structure, but it may not claim deployable alpha, portfolio value, or strategy usefulness.

Any supported association must enter a separately frozen confirmation campaign. Only a confirmed candidate may later enter a separately authorized incremental economic-value comparison against untouched Core v1.

## Current authorization

**Decision:** GO for Campaign #48 specification design and freeze preparation only.

Authorized now:

- update `docs/ITERA_CAMPAIGN_BOARD.md` for the Campaign #48 design transition;
- draft `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES.md`;
- define a small and interpretable predictor inventory;
- define exact source identities and source immutability checks;
- define deterministic anchor construction and chronological partitions;
- define exact forward outcomes and horizons;
- define leakage-safe controls and development-only transformations;
- define estimator, support, rankability, directional-consistency, and multiplicity rules;
- define deterministic serialization, replay, preflight, and stop conditions;
- preserve null, missing, failed, and insufficient-support candidates;
- review and freeze the specification before any predictive outcome generation.

Not authorized:

- generating, calculating, viewing, or inspecting predictive outcomes;
- implementing the Campaign #48 analysis pipeline;
- creating candidate rankings or statistical results;
- choosing features, windows, outcomes, or methods after seeing results;
- indicator sweeps, parameter searches, optimization, or data-dependent feature selection;
- Core v1 overlay or incremental economic-value testing;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- changes to regimes, thresholds, classifiers, strategies, signals, orders, execution, NAV, exposure, dashboards, runtime, or model training;
- source substitution, interpolation, filling, resampling, nearest-row matching, synthetic bars, or leakage from evaluation periods.

## Campaign #48 design principles

The specification must remain:

- simple;
- interpretable;
- prespecified;
- deterministic;
- replay-safe;
- chronological;
- leakage-safe;
- observation-only;
- research-only;
- fail-closed.

The campaign must avoid an indicator zoo. Every predictor and window must have a clear economic or statistical rationale and must be frozen before outcomes are generated.

## Initial design questions to freeze

The specification must resolve:

1. the exact governed BTC source and source hash;
2. the anchor interval and earliest eligible timestamp;
3. the exact predictor list and trailing windows;
4. whether closely related windows are separate candidates or grouped families;
5. the exact forward outcome families;
6. the exact forward horizons;
7. the baseline and incremental model structures;
8. development-only scaling and chronological evaluation rules;
9. minimum pooled and partition support;
10. estimator and robust covariance method;
11. full-rank and finite-estimate requirements;
12. directional-consistency requirements;
13. multiplicity families and false-discovery control;
14. canonical outputs and deterministic ordering;
15. preflight, replay, source-immutability, and publication gates;
16. explicit interpretation boundaries.

## Authorized file surfaces

Campaign #48 design work may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES.md`.

Any implementation file, runner, test, artifact, runtime, or additional documentation surface requires a later explicit board transition.

## Campaign #48 design acceptance gates

1. Campaign #47 is closed before Campaign #48 begins. **Passed: `d8f8b23`.**
2. S-008 is selected as the next governed research priority. **Passed by this transition.**
3. The campaign is described in simple, non-alpha-claiming language. **Passed by this transition.**
4. The governed source identity and immutability contract are explicit. **Pending specification.**
5. The predictor inventory and all trailing windows are exact and finite. **Pending specification.**
6. Outcomes and horizons are exact and prespecified. **Pending specification.**
7. Chronological evaluation and leakage controls are exact. **Pending specification.**
8. Estimator, support, rankability, consistency, and multiplicity rules are exact. **Pending specification.**
9. Canonical outputs, replay, serialization, and failure visibility are exact. **Pending specification.**
10. The specification prohibits outcome generation before freeze. **Pending specification.**
11. No runtime, regime, threshold, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change occurs. **Must remain true.**

## Immediate sequence

1. Record the Campaign #48 design transition. **Completed by this board update.**
2. Draft the simple BTC price-state baseline specification. **Authorized next.**
3. Review predictor scope and remove unnecessary or duplicative features. **Pending.**
4. Freeze the specification before predictive outcome generation. **Pending.**
5. Draft and freeze a separate implementation handoff. **Not yet authorized.**
6. Record a separate implementation GO only after final governance review. **Not yet authorized.**
7. Generate predictive outcomes only after all preceding gates pass. **Prohibited now.**

## Campaign #47 completion record

**Campaign:** Campaign #47 - Historical Regime Persistence, Duration, Clustering, and Spacing Discovery

**Final status:** COMPLETE - canonical artifacts published; zero rankable candidates and zero supported research associations

**Working branch:** `agent/campaign-47-regime-structure-implementation`

**Publication commit:** `16692c1`

Completed evidence:

- focused suite: `21 passed`;
- governed preflight before generation: `PASS`;
- predictive outcomes generated during preflight: `false`;
- canonical Campaign #46 source ledger: `70,069` states, `2,790` runs, and `2,789` transitions;
- common 168-hour anchor grid: `403` anchors;
- chronological partitions: `135`, `134`, `134`;
- frozen candidate inventory: `72`;
- pooled OLS-HC3 fits passing estimator requirements: `48`;
- pooled fits failing closed because a one-observation `HIGH_VOL` fixed-effect level produced unit leverage and undefined HC3: `24`;
- partition-2 designs failing the frozen full-rank requirement: `72`;
- partition-3 designs failing the frozen full-rank requirement: `72`;
- rankable candidates: `0`;
- candidates entering Benjamini-Hochberg correction: `0`;
- supported research associations: `0`;
- all failed and unrankable candidates remained visible in the canonical outputs;
- two governed canonical runs completed successfully;
- all ten canonical outputs were byte-identical across replay;
- all ten committed canonical outputs are UTF-8 and LF-only;
- governed Campaign #46 and BTC source bytes were unchanged before and after generation;
- full repository suite: `504 passed`, `75 warnings`;
- implementation comparison from GO commit `0529611` contained exactly the three authorized implementation paths before artifact publication;
- final publication added exactly the ten authorized Campaign #47 artifact paths;
- no runtime, threshold, regime, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training surface changed.

Campaign #47 conclusion:

Under the frozen development-defined fixed-effect, full-rank, HC3, chronological-evaluation, and fail-closed requirements, none of the 72 prespecified temporal regime-structure candidates was rankable. The historical ledger did not provide sufficient chronological regime-level support for a governed multiplicity-adjusted association test.

This is a negative and support-limited research result. It does not establish that regime duration, persistence, clustering, or spacing are intrinsically noninformative. It authorizes no Core v1 overlay test and no runtime, threshold, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Campaign #45 completion record

**Campaign:** Campaign #45 — Historical Regime State and Transition Discovery

**Final status:** COMPLETE — canonical artifacts published; no supported exact ordered-transition association

**Working branch:** `agent/campaign-45-historical-regime-transitions`

**Publication commit:** `5fa4b8434ed4927e69b8cc973ba0009f99215a24`

**Pull request:** PR #43

**Governed merge commit:** `42e5d7c47d90e1941e61e0e229d4fa71da07b449`

Completed evidence:

- focused suite: `24 passed`;
- governed preflight: `PASS`;
- source transitions: `2,789`;
- eligible non-`UNKNOWN` transitions: `2,788`;
- independent 168-hour-purged anchors: `242`;
- partitions: `81`, `81`, `80`;
- candidate-horizon tests: `51`;
- rankable candidates: `9`;
- insufficient binary-side support: `42`;
- supported associations: `0`;
- two governed runs completed successfully;
- all ten canonical outputs byte-identical across replay;
- canonical staged files LF-only and reconciled to their manifest;
- governed source bytes unchanged before and after generation;
- full repository suite: `483 passed`, `75 warnings`;
- final Campaign #45 comparison: exactly `13` authorized paths;
- branch diff check: clean.

Campaign #45 conclusion:

No exact ordered BTC regime transition met the frozen multiplicity-adjusted and directional-consistency requirements for incremental 24-hour, 72-hour, or 168-hour forward-return association after controlling for the six frozen BTC price-state controls.

This negative result weakens exact ordered-transition identity as a standalone predictive feature. It does not show that regimes, duration, persistence, clustering, volatility conditioning, risk estimation, or later confirmed overlays are useless. It authorizes no runtime, threshold, signal, strategy, order, portfolio, NAV, exposure, dashboard, or model-training change.

## Campaign #46 completion record

**Campaign:** Campaign #46 — Full Historical Regime State Sequence

**Final status:** COMPLETE — canonical artifacts published; `CAMPAIGN_45_SOURCE_FEASIBLE`

**Working branch:** `agent/campaign-46-full-regime-state-source`

**Canonical publication commit:** `34a6999`

Completed evidence:

- focused suite: `10 passed`;
- governed preflight: `PASS`;
- two-run replay: all eight files byte-identical;
- state rows: `70,069`;
- total transitions: `2,789`;
- eligible transitions: `2,788`;
- independent purged transitions: `242`;
- partition counts: `81`, `81`, `80`;
- predictive outcomes generated: `false`;
- full repository suite: `459 passed`, `75 warnings`.

Campaign #46 made no predictive, economic, directional, or alpha claim.

## Research-priority context

Campaign #44 ranked:

1. S-002 — Historical regime state and transition structure: 29;
2. S-003 — Historical event persistence, clustering, duration, and spacing: 27;
3. S-008 — Simple BTC price-state baselines: 26;
4. S-001 — Registered Core v1 collapse structure candidate A-001: 26.

Campaign #45 completed the governed predictive test of sparse exact ordered-transition identity for S-002. Campaign #47 advances S-003 using broadly supported continuous temporal structure rather than exact transition categories.

## Research progression boundary

Campaign #47 is a discovery campaign. Any supported association must enter a separately frozen confirmation campaign. Only candidates that survive confirmation may enter a later separately authorized incremental-value comparison against untouched Core v1 using Sharpe, CAGR, drawdown, turnover, exposure, and related economic metrics.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #47 unless separately authorized.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #47 authorization.
