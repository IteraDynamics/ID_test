# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #48 - Simple BTC Price-State Predictive Baselines

**Final status:** COMPLETE - canonical artifacts published; 15 supported research associations under the frozen discovery design

**Governance branch:** `agent/campaign-48-simple-btc-price-state-baselines-governance`

**Implementation branch:** `agent/campaign-48-simple-btc-price-state-baselines-implementation`

**Repository:** `IteraDynamics/ID_test`

**Governed lineage base:** Campaign #47 closure `d8f8b234ccd342369d3d134e1dd7d7b916557b0a`

**Specification freeze commit:** `e8777df3442d093fd84fb92c25d13aadc2bfe1ed`

**Implementation handoff freeze commit:** `a16c152608df481a66a2e29f7a1d7795b5490459`

**Initial implementation GO:** `99a7db937f68bb16662c4d28701f1cd52e661f36`

**Source-cadence amendment:** `d9fc7e7103a5033a9dbbe06b7abf93aea27d863b`

**Canonical artifact publication commit:** `fd7ee01`

## Campaign #48 question

> Does BTC's recent price behavior contain reliable information about what happens next?

Campaign #48 tested eight prespecified recent-return, realized-volatility, and price-location predictors against future directional return, absolute return, and realized volatility at exact 24-hour, 72-hour, and 168-hour horizons.

It was a research-only predictive-baseline discovery campaign, not a trading-strategy backtest.

## Governed source and corrective amendment

The only authorized source was:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- byte count: `4,792,028`;
- data rows: `70,069`;
- timestamps: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`;
- exact ordered schema: `timestamp`, `open`, `high`, `low`, `close`, `volume`.

The first governed preflight failed closed with `SOURCE_CADENCE_FAILURE` and `predictive_outcomes_generated:false`. An observation-only reconciliation established exactly 36 governed missing hourly timestamps. The board amendment at `d9fc7e7` superseded only the contradictory gapless-cadence language.

The corrected frozen rule required timestamps to be timezone-naive, unique, strictly increasing, and aligned to whole hours; required the full missing-hour inventory to equal the exact governed 36 timestamps; prohibited interpolation, filling, resampling, matching, shifting, synthetic bars, or repair; and treated incomplete predictor and outcome windows as unavailable.

No predictor, outcome, horizon, anchor spacing, chronological partition rule, estimator, standardization rule, support threshold, directional-consistency rule, multiplicity family, interpretation boundary, runtime behavior, or strategy behavior changed.

## Completed evidence

- corrected focused suite: `27 passed`;
- governed preflight: `PASS`;
- predictive outcomes generated during preflight: `false`;
- governed missing hourly timestamps: `36`;
- source rows: `70,069`;
- continuous hourly positions implied by endpoints: `70,105`;
- common 168-hour anchor grid: `403` retained anchors;
- chronological partitions: `135`, `134`, `134`;
- predictors: `8`;
- outcome families: `3`;
- horizons: `3`;
- candidate inventory: `72`;
- rankable candidates: `72`;
- directionally consistent candidates: `48`;
- supported research associations: `15`;
- multiplicity not met: `55`;
- multiplicity met but direction inconsistent: `2`;
- insufficient-support candidates: `0`;
- unavailable candidates: `0`;
- variance failures: `0`;
- rank-deficient designs: `0`;
- estimator failures: `0`;
- two governed canonical runs completed successfully;
- all ten canonical outputs were byte-identical across replay;
- post-generation preflight passed with `predictive_outcomes_generated:false`;
- governed source SHA-256 remained unchanged;
- full repository suite: `531 passed`, `75 warnings`;
- implementation scope from GO commit contained only the authorized board, analysis module, runner, focused test file, and ten canonical artifact files;
- no runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training surface changed.

## Campaign #48 result

All 15 supported associations were concentrated in volatility-state persistence and drawdown-linked future volatility.

Supported groups:

1. trailing 24-hour realized volatility positively associated with future absolute return at 24, 72, and 168 hours;
2. trailing 24-hour realized volatility positively associated with future realized volatility at 24, 72, and 168 hours;
3. trailing 168-hour realized volatility positively associated with future absolute return at 24, 72, and 168 hours;
4. trailing 168-hour realized volatility positively associated with future realized volatility at 24, 72, and 168 hours;
5. deeper drawdown from the trailing 168-hour high associated with higher future realized volatility at 24, 72, and 168 hours.

No directional-return candidate was supported.

Campaign #48 therefore establishes a transparent BTC price-state predictive baseline for future research: simple recent volatility and drawdown information contains reproducible association with the magnitude and volatility of subsequent movement, but not with direction under this frozen design.

## Interpretation boundary

This is a positive research result only. It does not establish deployable alpha, economic value, transaction-cost robustness, portfolio improvement, sizing value, timing value, superiority to Core v1, or production readiness.

Any supported Campaign #48 candidate must enter a separately frozen confirmation campaign before any incremental economic-value or Core v1 comparison.

Campaign #48 authorizes no runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Current authorization

**Decision:** Campaign #48 is closed. No further Campaign #48 implementation, artifact, result, runtime, or strategy work is authorized.

The next research campaign requires a separate board transition and explicit authorization before design or implementation begins.

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
- rankable candidates: `0`;
- supported research associations: `0`;
- two governed canonical runs completed successfully;
- all ten canonical outputs were byte-identical and LF-only;
- governed source bytes remained unchanged;
- full repository suite: `504 passed`, `75 warnings`.

Campaign #47 conclusion:

Under the frozen development-defined fixed-effect, full-rank, HC3, chronological-evaluation, and fail-closed requirements, none of the 72 prespecified temporal regime-structure candidates was rankable. This was a negative and support-limited result and authorized no Core v1 or runtime change.

## Campaign #45 completion record

**Campaign:** Campaign #45 - Historical Regime State and Transition Discovery

**Final status:** COMPLETE - canonical artifacts published; no supported exact ordered-transition association

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
- all ten canonical outputs replayed byte-identically;
- governed source bytes remained unchanged;
- full repository suite: `483 passed`, `75 warnings`.

Campaign #45 conclusion:

No exact ordered BTC regime transition met the frozen multiplicity-adjusted and directional-consistency requirements for incremental 24-hour, 72-hour, or 168-hour forward-return association after controlling for the six frozen BTC price-state controls. No runtime or strategy change was authorized.

## Campaign #46 completion record

**Campaign:** Campaign #46 - Full Historical Regime State Sequence

**Final status:** COMPLETE - canonical artifacts published; `CAMPAIGN_45_SOURCE_FEASIBLE`

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

Campaign #44 ranked S-002 first, S-003 second, and S-008 and S-001 tied next. Campaign #45 completed S-002. Campaign #47 completed S-003. Campaign #48 completed S-008 and established the transparent simple-price-state predictive hurdle for later candidates.

## Research progression boundary

Campaign #48 is a discovery campaign. Its supported associations require a separately frozen confirmation campaign. Only candidates surviving confirmation may enter a later separately authorized incremental-value comparison against untouched Core v1.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested unless separately authorized.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand current authorization.
