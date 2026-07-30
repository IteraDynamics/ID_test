# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #48 - Simple BTC Price-State Predictive Baselines

**Classification:** Research-only predictive-baseline discovery over the frozen governed BTC hourly source

**Status:** SPECIFICATION FROZEN - implementation handoff drafting and freezing are authorized; implementation, predictive outcomes, result inspection, economic testing, and runtime changes remain prohibited

**Working branch:** `agent/campaign-48-simple-btc-price-state-baselines-governance`

**Repository:** `IteraDynamics/ID_test`

**Governed lineage base:** Campaign #47 closure `d8f8b234ccd342369d3d134e1dd7d7b916557b0a`

**Governing specification:** `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES.md`

**Specification freeze commit:** `e8777df3442d093fd84fb92c25d13aadc2bfe1ed`

**Planned implementation handoff:** `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES_IMPLEMENTATION_HANDOFF.md`

## Plain-English objective

Campaign #48 asks:

> Does BTC's recent price behavior contain reliable information about what happens next?

Before Itera attributes predictive value to regimes, transitions, machine learning, or more complicated signal logic, it needs a transparent baseline showing what ordinary BTC price history can already explain.

The frozen study contains a small, prespecified set of recent-return, realized-volatility, and price-location predictors. It tests their statistical association with future directional return, absolute return, and realized volatility at exact 24-hour, 72-hour, and 168-hour horizons.

## Research role

Campaign #48 is a predictive-baseline discovery campaign, not a trading-strategy backtest.

It may establish a reproducible statistical association under the frozen design. It may not claim deployable alpha, portfolio value, economic usefulness, superiority to Core v1, or production readiness.

Any supported association must enter a separately frozen confirmation campaign. Only a confirmed candidate may later enter a separately authorized incremental economic-value comparison against untouched Core v1.

## Frozen Campaign #48 research contract

### Source

Only the following source is authorized:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- byte count: `4,792,028`;
- data rows: `70,069`;
- timestamps: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`;
- exact ordered schema: `timestamp`, `open`, `high`, `low`, `close`, `volume`;
- exact hourly cadence.

Only `timestamp` and `close` may enter Campaign #48 predictor or outcome calculations.

### Anchors and partitions

- one deterministic 168-hour anchor grid;
- origin at the earliest timestamp with every exact close in `[t-168h, t]`;
- exact 168-hour increments only;
- three contiguous near-equal chronological partitions;
- remainder anchors assigned to earlier partitions;
- no shifting, replacement, filling, interpolation, resampling, or timestamp repair.

### Predictors

Exactly eight predictors:

1. trailing 24-hour log return;
2. trailing 72-hour log return;
3. trailing 168-hour log return;
4. trailing 24-hour realized volatility;
5. trailing 168-hour realized volatility;
6. distance from trailing 168-hour close mean;
7. position within trailing 168-hour close range;
8. drawdown from trailing 168-hour close high.

No indicator sweep, thresholds, bins, labels, interactions, splines, polynomial terms, learned features, or data-dependent feature selection are authorized.

### Outcomes and candidate family

At exact 24-hour, 72-hour, and 168-hour horizons:

- Family R: directional forward log return;
- Family M: absolute forward log return;
- Family V: forward realized volatility.

Candidate inventory:

- 8 predictors;
- 3 outcome families;
- 3 horizons;
- 72 total candidates.

### Estimator and evaluation

Each candidate uses:

- OLS with intercept;
- exactly one standardized predictor;
- no regime labels or fixed effects;
- no additional price controls;
- HC3 covariance;
- two-sided normal p-value;
- 95% normal confidence interval.

Chronological evaluation uses development-only predictor standardization with population standard deviation, equivalent to `numpy.std(values, ddof=0)`.

Required fits are pooled, partition-2 evaluation using partition 1 development statistics, and partition-3 evaluation using partitions 1 and 2 development statistics.

### Support, consistency, and multiplicity

A candidate requires at least:

- 90 candidate-complete pooled anchors;
- 25 candidate-complete anchors in each chronological partition;
- finite predictor and outcome values;
- finite development mean and strictly positive population standard deviation;
- full-rank pooled, partition-2, and partition-3 designs;
- finite nonzero coefficients;
- finite strictly positive HC3 standard errors;
- finite pooled p-value.

Directional consistency requires the same nonzero coefficient sign in pooled, partition-2, and partition-3 fits.

Benjamini-Hochberg FDR at `q = 0.05` is applied separately within three 24-test outcome families. Only rankable candidates enter BH; all failed and unrankable candidates remain visible.

### Planned outputs

A future implementation handoff must define exact schemas and deterministic ordering for exactly ten outputs under:

`artifacts/simple_btc_price_state_predictive_baselines/`

No output may contain wall-clock timestamps, absolute machine paths, random identifiers, unordered mappings, or nonfinite JSON values. Canonical text must be UTF-8 and LF-only.

## Current authorization

**Decision:** The Campaign #48 specification is frozen. GO for implementation-handoff drafting and freeze preparation only.

Authorized now:

- update `docs/ITERA_CAMPAIGN_BOARD.md` for Campaign #48 governance;
- preserve the frozen specification without amendment;
- draft `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES_IMPLEMENTATION_HANDOFF.md`;
- define exact implementation file surfaces without creating them;
- define exact function, schema, status, ordering, serialization, preflight, replay, and test contracts;
- reconcile the handoff exactly to specification freeze `e8777df3442d093fd84fb92c25d13aadc2bfe1ed`;
- freeze the handoff before any implementation or predictive outcome generation;
- conduct a final governance review before any implementation GO.

Not authorized:

- amending the frozen specification;
- implementation code;
- runner code;
- tests;
- artifacts;
- generating, calculating, viewing, or inspecting predictive outcomes;
- candidate ranking or statistical results;
- choosing features, windows, outcomes, or methods after seeing results;
- Core v1 overlay or incremental economic-value testing;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- changes to regimes, thresholds, classifiers, strategies, signals, orders, execution, NAV, exposure, dashboards, runtime, or model training;
- source substitution, interpolation, filling, resampling, nearest-row matching, synthetic bars, or leakage from evaluation periods.

## Authorized file surfaces

Campaign #48 governance may modify only:

- `docs/ITERA_CAMPAIGN_BOARD.md`;
- `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES.md` only as the already-frozen specification;
- `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES_IMPLEMENTATION_HANDOFF.md`.

Any implementation, runner, test, artifact, runtime, or additional documentation surface requires a later explicit board transition.

## Campaign #48 acceptance gates

1. Campaign #47 is closed before Campaign #48 begins. **Passed: `d8f8b23`.**
2. S-008 is selected as the next governed research priority. **Passed: `58887e0`.**
3. The campaign is described in simple, non-alpha-claiming language. **Passed.**
4. The governed source identity, exact schema, and immutability contract are explicit. **Passed: `e8777df`.**
5. The predictor inventory and all trailing windows are exact and finite. **Passed: `e8777df`.**
6. Outcomes and horizons are exact and prespecified. **Passed: `e8777df`.**
7. Chronological evaluation and leakage controls are exact. **Passed: `e8777df`.**
8. Estimator, support, rankability, consistency, and multiplicity rules are exact. **Passed: `e8777df`.**
9. Canonical outputs, replay, serialization, and failure visibility are exact at specification level. **Passed: `e8777df`; exact schemas pending handoff.**
10. The specification prohibits outcome generation before freeze and implementation GO. **Passed: `e8777df`.**
11. A separate implementation handoff predates predictive outcome generation. **Pending.**
12. A separate implementation GO is recorded only after final governance review. **Pending.**
13. No runtime, regime, threshold, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change occurs. **Must remain true.**

## Immediate sequence

1. Record the Campaign #48 design transition. **Completed: `58887e0`.**
2. Draft and review the simple BTC price-state baseline specification. **Completed.**
3. Review predictor scope and remove unnecessary features. **Completed: eight frozen predictors retained.**
4. Freeze the specification before predictive outcome generation. **Completed: `e8777df`.**
5. Draft and freeze a separate implementation handoff. **Authorized next.**
6. Conduct final governance review. **Pending.**
7. Record a separate implementation GO only after review. **Pending.**
8. Generate predictive outcomes only after all preceding gates pass. **Prohibited now.**

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

Campaign #45 completed S-002. Campaign #47 completed S-003. Campaign #48 advances S-008 as the transparent predictive hurdle for later candidates.

## Research progression boundary

Campaign #48 is a discovery campaign. Any supported association must enter a separately frozen confirmation campaign. Only candidates that survive confirmation may enter a later separately authorized incremental-value comparison against untouched Core v1 using Sharpe, CAGR, drawdown, turnover, exposure, and related economic metrics.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #48 unless separately authorized.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #48 authorization.
